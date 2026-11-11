"""Cloud-only agent runner using an OpenAI-compatible Chat Completions API."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from uuid import uuid4
import company as ledger

ROOT = ledger.ROOT

def configuration(role):
    config = ledger.read('cloud.json')
    options = dict(config['defaults'])
    options.update(config.get('roles', {}).get(role, {}))
    for key in ['base_url', 'model']:
        if not options.get(key):
            options[key] = os.environ.get('LLM_' + key.upper(), '')
    key = os.environ.get(options['api_key_env'], '')
    if not key or not options['model']:
        raise ValueError('Set LLM_API_KEY and LLM_MODEL in the process environment, or configure the role provider.')
    url = urlparse(options['base_url'])
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('Cloud base_url must be an HTTPS URL without credentials, query or fragment')
    if not isinstance(options['max_output_tokens'], int) or not 1 <= options['max_output_tokens'] <= 16000:
        raise ValueError('max_output_tokens must be between 1 and 16000')
    return options, key

class NoRedirect(__import__('urllib.request', fromlist=['HTTPRedirectHandler']).HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('API redirect refused; configure the intended provider URL explicitly')

def call(options, key, messages):
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
                    base_url=options['base_url'], model=options['model'], messages=messages)
    (history/'request.json').write_text(json.dumps(metadata, indent=2))
    ledger.event('cloud_started', task_id=task_id, attempt=attempt, model=options['model'])
    try:
        text, usage = call(options, key, messages)
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
    parser.add_argument('task_id', help='An owner-approved task; one billable request per invocation')
    args = parser.parse_args()
    try:
        print(run(args.task_id))
    except (ValueError, KeyError, OSError) as error:
        print('Error: '+str(error), file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
