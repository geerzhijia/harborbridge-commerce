"""Cloud-only agent runner supporting Gemini and OpenAI-compatible APIs."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.request import Request
from urllib.error import HTTPError
from urllib.parse import urlparse
from uuid import uuid4
import company as ledger

ROOT = ledger.ROOT

def configuration(role):
    config = ledger.read('cloud.json')
    options = dict(config['defaults'])
    options.update(config.get('roles', {}).get(role, {}))
    options.setdefault('provider', 'openai_compatible')
    if options['provider'] not in {'gemini', 'openai_compatible'}:
        raise ValueError('provider must be gemini or openai_compatible')
    for key in ['base_url', 'model']:
        if not options.get(key):
            options[key] = os.environ.get('LLM_' + key.upper(), '')
    key = os.environ.get(options['api_key_env'], '')
    if not key or not options['model']:
        raise ValueError('Set '+options['api_key_env']+' and configure a model in cloud.json or LLM_MODEL.')
    url = urlparse(options['base_url'])
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('Cloud base_url must be an HTTPS URL without credentials, query or fragment')
    if not isinstance(options['max_output_tokens'], int) or not 1 <= options['max_output_tokens'] <= 16000:
        raise ValueError('max_output_tokens must be between 1 and 16000')
    if options['provider'] == 'gemini':
        import re
        if not re.fullmatch(r'[A-Za-z0-9._-]+', options['model']):
            raise ValueError('Gemini model must be a model ID without a path')
        if url.hostname != 'generativelanguage.googleapis.com':
            raise ValueError('Gemini requires the official Google API hostname')
    timeout = options.get('timeout_seconds')
    if not isinstance(timeout, (float, int)) or not 1 <= timeout <= 300:
        raise ValueError('timeout_seconds must be between 1 and 300')
    return options, key

class NoRedirect(__import__('urllib.request', fromlist=['HTTPRedirectHandler']).HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('API redirect refused; configure the intended provider URL explicitly')

def call_openai(options, key, messages):
    body = dict(model=options['model'], messages=messages, max_completion_tokens=options['max_output_tokens'])
    request = Request(options['base_url'].rstrip('/') + '/chat/completions',
                      data=json.dumps(body).encode(),
                      headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    from urllib.request import build_opener
    with build_opener(NoRedirect()).open(request, timeout=options['timeout_seconds']) as response:
        result = json.load(response)
    choice = result['choices'][0]
    if choice.get('finish_reason') != 'stop':
        raise ValueError('Provider did not finish normally; task remains approved for review/retry')
    content = choice['message'].get('content')
    if not isinstance(content, str) or not content.strip():
        raise ValueError('Provider returned no text report')
    return content, result.get('usage', {})

def call_gemini(options, key, messages):
    systems = [m['content'] for m in messages if m['role'] == 'system']
    contents = [{'role': 'model' if m['role'] == 'assistant' else 'user',
                 'parts': [{'text': m['content']}]} for m in messages if m['role'] != 'system']
    body = {'contents': contents, 'generationConfig': {'maxOutputTokens': options['max_output_tokens']}}
    if systems:
        body['systemInstruction'] = {'parts': [{'text': '\n\n'.join(systems)}]}
    request = Request(options['base_url'].rstrip('/') + '/models/' + options['model'] + ':generateContent',
                      data=json.dumps(body).encode(),
                      headers={'x-goog-api-key': key, 'Content-Type': 'application/json'})
    from urllib.request import build_opener
    with build_opener(NoRedirect()).open(request, timeout=options['timeout_seconds']) as response:
        result = json.load(response)
    candidates = result.get('candidates', [])
    if not candidates or candidates[0].get('finishReason') != 'STOP':
        raise ValueError('Gemini blocked or did not complete the report; no automatic retry')
    parts = candidates[0].get('content', {}).get('parts', [])
    content = ''.join(p.get('text', '') for p in parts if not p.get('thought'))
    if not content.strip():
        raise ValueError('Gemini returned no text report')
    return content, result.get('usageMetadata', {})

def call(options, key, messages):
    if options.get('provider', 'openai_compatible') == 'gemini':
        return call_gemini(options, key, messages)
    return call_openai(options, key, messages)

def run(task_id):
    task = ledger.read('state/tasks.json', {})[task_id]
    if task['status'] != 'approved':
        raise ValueError('Owner must approve this task before any cloud request')
    # Resolve policy/config before sending anything; no automatic retries or tool calls.
    options, key = configuration(task['role'])
    context = subprocess.check_output([sys.executable, str(ROOT/'tools/company.py'), 'context', task['role']], text=True)
    messages = [
        {'role':'system', 'content':context + '\nYou have no browsing, external tools or live monitoring. Do not invent current facts. Work only on the selected task. Return a draft report for owner review; identify missing data and human actions. Never claim to have contacted anyone or executed actions.'},
        {'role':'user', 'content':'Selected approved task ' + task_id + ':\n' + task['description']}
    ]
    attempt = uuid4().hex
    history = ROOT/'state/runs'/attempt
    history.mkdir(parents=True)
    metadata = dict(task_id=task_id, role=task['role'], attempt=attempt, started_at=ledger.now(),
                    provider=options.get('provider', 'openai_compatible'),
                    base_url=options['base_url'], model=options['model'], messages=messages)
    (history/'request.json').write_text(json.dumps(metadata, indent=2))
    ledger.event('cloud_started', task_id=task_id, attempt=attempt, model=options['model'])
    try:
        text, usage = call(options, key, messages)
    except HTTPError as error:
        ledger.event('cloud_failed', task_id=task_id, attempt=attempt, http_status=error.code)
        hint = {401: 'Check the API key.', 403: 'Check API key permissions, project access and region.',
                404: 'Check model availability and endpoint.', 429: 'Quota or rate limit reached; check AI Studio and wait before retrying.'}.get(error.code, 'Check provider status and configuration.')
        raise ValueError('Cloud HTTP '+str(error.code)+'. '+hint+' No automatic retry or provider fallback.') from None
    except Exception:
        # Do not persist exception payloads: providers may include sensitive request data.
        ledger.event('cloud_failed', task_id=task_id, attempt=attempt)
        raise ValueError('Cloud request failed; task remains approved. No automatic retry. Check provider settings/status and billing before retrying.') from None
    (history/'response.json').write_text(json.dumps(dict(text=text, usage=usage, completed_at=ledger.now()), indent=2))
    report = ROOT/'reports'/(task_id+'-'+attempt+'.md')
    report.write_text('# Cloud-generated draft — requires owner review\n\n'+text+'\n')
    tasks = ledger.read('state/tasks.json', {})
    if tasks[task_id]['status'] != 'approved':
        raise ValueError('Task changed during request; result saved but task was not updated')
    tasks[task_id].update(status='awaiting_owner_review', report=str(report.relative_to(ROOT)), updated_at=ledger.now())
    ledger.write('state/tasks.json', tasks)
    ledger.write('state/checkpoints/'+task['role']+'.json', dict(role=task['role'], updated_at=ledger.now(),
        summary='Cloud draft saved; owner review required', task_id=task_id, report=str(report.relative_to(ROOT)), attempt=attempt))
    ledger.event('cloud_completed', task_id=task_id, attempt=attempt, report=str(report.relative_to(ROOT)), usage=usage)
    return str(report.relative_to(ROOT))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task_id', nargs='?', help='An owner-approved task; one API request per invocation')
    parser.add_argument('--check-config', metavar='ROLE', help='Validate configuration and key presence without an API call')
    args = parser.parse_args()
    try:
        if args.check_config:
            if args.check_config not in ledger.read('agents/registry.json', {}):
                raise ValueError('Unknown role')
            options, _ = configuration(args.check_config)
            print(json.dumps({k: options[k] for k in ['provider', 'model', 'base_url', 'api_key_env', 'max_output_tokens']}, indent=2))
            print('Configuration valid and key present. No API request made; project billing tier is not verified.')
        elif args.task_id:
            print(run(args.task_id))
        else:
            parser.error('Provide task_id or --check-config ROLE')
    except (ValueError, KeyError, OSError) as error:
        print('Error: '+str(error), file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
