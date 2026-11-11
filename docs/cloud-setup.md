# Run every role with a cloud LLM
No local model or GPU is needed. All seven roles use a hosted API; a role is a separate prompt and saved state, so you do not need seven simultaneous model servers. The runner makes one API request for a selected approved task, saves its result, then stops. It is not an always-on background service. Run one process at a time with this single-owner ledger.

## Gemini free-tier test (current default)
All roles currently use native Gemini generateContent with `gemini-3.5-flash-lite`, 2,000 maximum output tokens and no browsing/tool calls. Google currently lists this model with free-tier input/output. Confirm availability, project tier and quotas in Google AI Studio: https://aistudio.google.com/api-keys . Use a project on the **Free** tier for this test. Setting a model ID or a `free` label in this repository cannot prevent charges on a paid project. No automatic fallback to another model/provider is configured.

```bash
cd /workspace/source/harborbridge-commerce
read -rs -p 'Gemini API key: ' GEMINI_API_KEY; echo
export GEMINI_API_KEY
python3 tools/cloud.py --check-config ceo
# Owner approves the existing CEO task; then run it:
python3 tools/company.py approve task-7f57b1072fa6 --by owner
python3 tools/cloud.py task-7f57b1072fa6
```

The API key belongs to your Google project. Never paste it into chat or commit it. Environment variables last for the current terminal session; use a secret manager for persistence. `.env` files are not automatically loaded. `--check-config` checks local settings and key presence only, with no network call. If quota is exhausted, the run fails and waits; it does not switch to a paid model. If a run fails, inspect its status before retrying; do not approve an already approved task again.

Free-tier content may be used to improve Google's products. Use nonsensitive test information. Current terms, rates and quotas: https://ai.google.dev/gemini-api/docs/pricing and https://ai.google.dev/gemini-api/docs/rate-limits . No live free-tier access or billing status has been verified for your account.

## Change provider/model
`cloud.json` controls execution. `defaults` applies to all roles; `roles` merges overrides for specific roles. A Gemini example is saved in `examples/cloud-gemini.json`; an OpenAI-compatible example is in `examples/cloud-openai.json`. Copy the desired example to cloud.json and edit it. Nothing installs or runs a local model.

```json
{"ceo": {"model": "another-gemini-model-id"}}
```

Place that object under `roles` to change only the CEO. To switch a role to OpenAI or another compatible API, override **all four** provider fields together:

```json
{"finance": {"provider": "openai_compatible", "base_url": "https://api.openai.com/v1", "model": "your-model-id", "api_key_env": "OPENAI_API_KEY"}}
```

Set that provider's key in its named environment variable. OpenAI API billing is separate from ChatGPT subscriptions. Existing configs without `provider` continue to use the OpenAI-compatible adapter. That adapter expects `/chat/completions`, bearer authentication, `max_completion_tokens` and string text responses. Gemini uses the native `/models/MODEL:generateContent` API with `x-goog-api-key`. Native Anthropic APIs still require a separate adapter or compatible gateway.

Model/base URL values in cloud.json take precedence. If either is empty, the runner reads LLM_MODEL / LLM_BASE_URL respectively. Registry model/provider fields are descriptive placeholders, not runtime configuration. Exported config and prompts remain vendor independent; reconnect the selected provider's secret on migration.

Set provider-side spend limits and review rates before first use. max_output_tokens limits requested output, not dollars or total input tokens. Long context/history can increase charges. Failed requests can still be billed. There are no automatic retries, loops or scheduled calls. Configuration is owner-controlled. Ensure you are comfortable sending the role context, company config, task list and checkpoint to that provider; do not put secrets/customer data in these records.

The API runner has no tools: it cannot browse Google Trends/social media/1688, track shipments or operate Amazon. It produces draft analysis from supplied context and flags missing evidence. To analyze actual material, include vetted evidence in the approved task description; reports referenced by paths are not automatically loaded. Connecting research APIs/browser access and Amazon/carrier tools is a separate step requiring scoped permissions and approval enforcement.

CEO usage: create and approve a CEO task containing the specialist findings you want synthesized, then run that task with the same command. CEO can propose assignments; it cannot approve or execute new specialist tasks. You approve them before separate cloud runs. This respects the current owner_all policy.

Each attempt stores request context and response/usage in state/runs/, a report in reports/, and a checkpoint plus ledger events. Failed attempts retain the request but leave the task approved; inspect state before retry. Migration exports include these records, so store exports privately. API keys are read at runtime and never intentionally persisted. Move the repo to another host and reconnect its secrets to resume. For production concurrency add transactional locking, authenticated approval, durable job status and reconciliation before running multiple workers.
