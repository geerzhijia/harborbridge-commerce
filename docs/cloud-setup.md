# Run every role with a cloud LLM
No local model or GPU is needed. All seven roles use a hosted API; a role is a separate prompt and saved state, so you do not need seven simultaneous model servers. The runner makes one paid request for a selected approved task, saves its result, then stops. It is not an always-on background service. Run one process at a time with this single-owner ledger.

The default endpoint is OpenAI's Chat Completions API. Configure a model available to your API account. A ChatGPT subscription does not supply API credentials or API billing credits. Never send keys in chat, commit them or put them in task descriptions. Set environment variables via your shell or secret manager; `.env` files are not automatically loaded.

```sh
# In your terminal, supply your key without displaying it:
read -rs -p 'Cloud API key: ' LLM_API_KEY; echo
export LLM_API_KEY
export LLM_MODEL='your-provider-model-id'
python3 tools/company.py task market 'Draft a research plan for three product niches; identify required current data'
# Owner runs approval, using the returned task ID:
python3 tools/company.py approve TASK_ID --by owner
python3 tools/cloud.py TASK_ID
# Read the saved report; owner accepts it when satisfied:
python3 tools/company.py review TASK_ID --by owner
```

All roles inherit cloud.json defaults. Override any role under `roles`, for example:

```json
{"finance": {"model": "your-finance-model-id", "base_url": "https://your-provider.example/v1", "api_key_env": "FINANCE_API_KEY"}}
```

`roles` keys match agents/registry.json. LLM_BASE_URL overrides an empty base_url; to use a different provider, set base_url explicitly in cloud.json (or make it empty and use the environment variable). A provider must support HTTPS OpenAI-compatible `/chat/completions`, bearer authentication, `max_completion_tokens`, string message content and `finish_reason: stop`. Native Anthropic/Gemini APIs need an adapter or compatible gateway; arbitrary APIs are not interchangeable. Select providers and models that accept this contract. Registry provider/model fields remain descriptive placeholders; cloud.json controls runtime selection.

Set provider-side spend limits and review rates before first use. max_output_tokens limits requested output, not dollars or total input tokens. Long context/history can increase charges. Failed requests can still be billed. There are no automatic retries, loops or scheduled calls. Configuration is owner-controlled. Ensure you are comfortable sending the role context, company config, task list and checkpoint to that provider; do not put secrets/customer data in these records.

The API runner has no tools: it cannot browse Google Trends/social media/1688, track shipments or operate Amazon. It produces draft analysis from supplied context and flags missing evidence. To analyze actual material, include vetted evidence in the approved task description; reports referenced by paths are not automatically loaded. Connecting research APIs/browser access and Amazon/carrier tools is a separate step requiring scoped permissions and approval enforcement.

CEO usage: create and approve a CEO task containing the specialist findings you want synthesized, then run that task with the same command. CEO can propose assignments; it cannot approve or execute new specialist tasks. You approve them before separate cloud runs. This respects the current owner_all policy.

Each attempt stores request context and response/usage in state/runs/, a report in reports/, and a checkpoint plus ledger events. Failed attempts retain the request but leave the task approved; inspect state before retry. Migration exports include these records, so store exports privately. API keys are read at runtime and never intentionally persisted. Move the repo to another host and reconnect its secrets to resume. For production concurrency add transactional locking, authenticated approval, durable job status and reconciliation before running multiple workers.
