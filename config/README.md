# config

[`settings.toml`](settings.toml) lists every setting the service reads, at its default. It holds no
secrets: those go in `.env` (copy [`.env.example`](../.env.example)), and the service refuses to
start if a secret is written here.

## How a value is chosen

Highest first: an environment variable, then `.env`, then this file, then the default in
[`backend/intake_agent/config.py`](../backend/intake_agent/config.py). Each key's environment name is
its section and key joined by an underscore, in capitals: `[match] likely` is `MATCH_LIKELY`.
`SETTINGS_FILE` points the service at a different file. Every setting is logged at startup, secrets
masked, in the `service.start` event.

A test (`backend/tests/test_config.py`) keeps this file equal to the defaults in code, so the two
cannot drift. Settings that contradict each other stop the service at startup: a possible threshold
at or above the likely one, dev sign-in on an address other machines can reach, or Entra ID without
a tenant id and an audience.

## Every setting

| Setting | Default | What it does |
| --- | --- | --- |
| `[llm] provider` | `fake` | `anthropic`, `openai`, `azure`, or `fake`, the offline stand-in |
| `[llm] model` | `claude-sonnet-5-5` | The model that plays the agent |
| `[llm] judge_model` | `claude-sonnet-5-5` | Unused here: runs are scored by fixed checks |
| `[llm] embedding_model` | `text-embedding-3-small` | Unused here: names are matched without embeddings |
| `[llm] max_tokens` | `2048` | Unused here: `[agent] max_tokens` limits each call |
| `[llm] temperature` | `0.0` | 0 keeps runs repeatable |
| `[llm] max_retries` | `3` | Retries for model failures that can succeed later |
| `[llm] timeout_s` | `60.0` | How long one model call may take |
| `[azure_openai] endpoint` | unset | The Azure OpenAI resource; only for the `azure` provider |
| `[azure_openai] api_version` | `2024-10-21` | Only for the `azure` provider |
| `[eval] budget_usd` | `5.0` | A process stops calling the model once it has spent this |
| `[log] dir` | `logs` | Where the daily JSON log files go |
| `[log] level` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |
| `[log] redact` | `true` | Removes emails, phone numbers and ID-like numbers from log lines |
| `[log] trace` | `false` | Prints the logger lines (once switched on) as HH:MM:SS traces |
| `[data] firm` | `data/samples/firm.json` | The planted records the database is built around |
| `[data] database` | `data/generated/firm.sqlite` | The made-up firm database, built on first start |
| `[data] scenarios` | `data/evals/scenarios.jsonl` | The twenty evaluation scenarios |
| `[data] results` | `data/evals/results` | Where evaluation results are written |
| `[seed] random` | `11` | The seed; the same seed always builds the same database |
| `[seed] clients` | `300` | Clients, the planted ones included |
| `[seed] matters` | `180` | Existing matters |
| `[seed] adverse_parties` | `200` | Parties the firm has been against |
| `[seed] near_duplicate_share` | `0.2` | Made-up adverse parties that are a client's name, mistyped |
| `[seed] former_share` | `0.25` | Made-up clients the firm no longer acts for |
| `[seed] closed_share` | `0.35` | Made-up matters that are closed |
| `[match] likely` | `92` | From this score two names are likely one party |
| `[match] possible` | `80` | From this score a person must decide; below it, no match |
| `[match] limit` | `5` | The most matches one search returns |
| `[agent] max_steps` | `10` | The most model calls one run may make |
| `[agent] max_tool_calls` | `30` | The most tool calls one run may make |
| `[agent] max_tokens` | `1500` | The most tokens one model call may write |
| `[agent] run_budget_usd` | `0.5` | One run stops calling the model past this spend |
| `[agent] min_email_chars` | `20` | The shortest intake email accepted |
| `[agent] max_email_chars` | `20000` | The longest intake email accepted |
| `[agent] max_parties` | `10` | The most adverse parties one draft may name |
| `[store] timeout_s` | `2.0` | How long a query waits on a locked database |
| `[store] retries` | `2` | How many times a search retries a timed-out read |
| `[store] backoff_s` | `0.2` | The first wait between those retries; it doubles |
| `[api] host` | `127.0.0.1` | The address the server listens on: this machine only |
| `[api] port` | `8000` | The port |
| `[api] intakes_per_minute` | `6` | Per person; each intake calls the model |
| `[api] allowed_origins` | `http://localhost:5173` | Browser origins allowed to call the API |
| `[api] allowed_hosts` | `localhost`, `127.0.0.1` | Host names requests may be addressed to |
| `[api] min_reason_chars` | `10` | The shortest reason for approving past a flagged check |
| `[api] max_note_chars` | `500` | The longest decision note, at most 2,000; the web app holds the same 500 |
| `[auth] mode` | `dev` | `dev`: trusted headers, this machine only; `entra`: Entra ID tokens |
| `[entra] tenant_id` | empty | The directory (tenant) id, a GUID |
| `[entra] audience` | empty | The API's application (client) id, which tokens must be issued for |
| `[entra] requester_role` | `Intake.Requester` | The app role that may run intakes |
| `[entra] approver_role` | `Intake.Approver` | The app role that may approve and open matters |
| `[entra] leeway_s` | `60` | The clock skew allowed on token times |
| `[entra] keys_cache_s` | `3600` | How long the tenant's signing keys are cached |
| `[ui] examples` | `s04`, `s09`, `s13`, `s18` | The scenario ids the web app offers to try |

## Turning on Entra ID

In the tenant's app registration for this API: expose an API, add the app roles `Intake.Requester`
and `Intake.Approver` and assign them to people, and set `accessTokenAcceptedVersion` to 2 in the
manifest so tokens carry the v2.0 issuer. Then set `[auth] mode = "entra"`, `[entra] tenant_id` and
`[entra] audience` (the application id). No secret is needed: tokens are checked with the tenant's
published signing keys. The web app does not sign in to Entra ID yet; any client that sends a bearer
token can.
