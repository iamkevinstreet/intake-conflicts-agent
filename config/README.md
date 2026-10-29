# config

[`config.toml`](config.toml) lists every setting the service reads, and every value the service
and the web app share, at its default. It holds no secrets: those go in `config/.env` (copy
[`.env.example`](.env.example)), and the service refuses to start if a secret is written here.

## How a value is chosen

Highest first: an environment variable, then `config/.env`, then this file, then the default in
[`backend/src/intake_agent/config.py`](../backend/src/intake_agent/config.py). Each key's
environment name is its section and key joined by an underscore, in capitals: `[match] likely` is
`MATCH_LIKELY`. `SETTINGS_FILE` points the service at a different file. Every setting is logged at
startup, secrets masked, in the `service.start` event.

A test (`backend/tests/test_config.py`) keeps this file equal to the defaults in code, so the two
cannot drift. Settings that contradict each other stop the service at startup: a possible threshold
at or above the likely one, a default list longer than the most a list may hold, dev sign-in on an
address other machines can reach, or Entra ID without a tenant id and an audience.

The web app reads the keys it needs from this file when it is built (`frontend/vite.config.ts`):
the API's path and request id header, the email, reason and note limits, the match thresholds, and
the milliseconds in a second. It reads nothing from `config/.env`. Rebuild the web app after
changing one of them.

The values under `[ids]`, `[roles]`, `[verdicts]` and `[units]` are fixed: the service, its API and
the web app share them as they are, and the settings refuse any other value. They live here because
more than one file uses them.

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
| `[match] strong_bands` | `exact`, `likely` | The bands that count as the same party: a strong match with a current client, or in an open matter, is a conflict |
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
| `[api] port` | `8000` | The port; the web app's dev server proxies to this address |
| `[api] prefix` | `/api/v1` | The path every route lives under; the web app calls it |
| `[api] request_id_header` | `X-Request-ID` | The header that carries a request's id, both ways |
| `[api] intakes_per_minute` | `6` | Per person; each intake calls the model |
| `[api] allowed_origins` | `http://localhost:5173` | Browser origins allowed to call the API |
| `[api] allowed_hosts` | `localhost`, `127.0.0.1` | Host names requests may be addressed to |
| `[api] min_reason_chars` | `10` | The shortest reason for approving past a flagged check |
| `[api] max_note_chars` | `500` | The longest decision note, at most 2,000; the web app reads the same value |
| `[api] list_limit` | `50` | How many drafts or runs a list returns when none is asked for |
| `[api] max_list_limit` | `200` | The most drafts or runs a list may be asked for |
| `[ids] draft_pattern` | `^D-[0-9a-f]{10}$` | The shape of a draft id; any other is refused (fixed) |
| `[ids] run_pattern` | `^R-[0-9a-f]{10}$` | The shape of a run id; any other is refused (fixed) |
| `[roles] requester` | `requester` | The role that runs intakes (fixed) |
| `[roles] approver` | `approver` | The role that decides drafts and opens matters (fixed) |
| `[verdicts] clear` | `clear` | No record touches the new matter (fixed) |
| `[verdicts] review` | `review` | A person must decide (fixed) |
| `[verdicts] conflict` | `conflict` | The firm cannot take the matter as it stands (fixed) |
| `[units] ms_per_second` | `1000` | Milliseconds in a second, for timings in the logs and on screen (fixed) |
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
