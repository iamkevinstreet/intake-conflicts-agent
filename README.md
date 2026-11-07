# New-matter intake agent

[![ci](https://github.com/iamkevinstreet/intake-conflicts-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/iamkevinstreet/intake-conflicts-agent/actions/workflows/ci.yml)
[![codeql](https://github.com/iamkevinstreet/intake-conflicts-agent/actions/workflows/codeql.yml/badge.svg)](https://github.com/iamkevinstreet/intake-conflicts-agent/actions/workflows/codeql.yml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

An agent that reads a new-matter intake email, runs the conflicts searches with read-only tools, and
drafts the matter for an approver. It cannot open the matter. For firms that want an agent at intake
without giving it the power to act.

Case study: <https://kevindstreet.com/projects/intake-conflicts-check-agent/>

## Status

| | |
| --- | --- |
| Works today | The agent loop with five scoped tools, the conflicts rules, the approval gate (in the API and in the database), the audit log, Entra ID token checks in the API, the web app, the 20-scenario evaluation, offline and in CI, the dashboard and Tableau export over its results, spans of every run for Langfuse, and an MCP server that lets Claude Desktop or Claude Code play the agent behind the same gate |
| Measured | The 20 scenarios with `claude-sonnet-5-5` on GitHub's runner, Oct 29, 2026, rerun with its trace on Nov 7: every planted conflict found, no false alarm, every failure handled, no matter opened (below), beside the offline baseline |
| Next | Entra ID sign-in in the web app, whose tokens the API already checks; a harder scenario set, since this one is now passed in full |

Every client, matter, party and email here is made up. [`data/samples/firm.json`](data/samples/firm.json)
plants the records the scenarios are written around, and a seeded generator adds about 500 names
around them.

## Quick start

Needs [uv](https://docs.astral.sh/uv/) and Node 24. No API key: offline, fixed rules play the
agent.

```sh
git clone https://github.com/iamkevinstreet/intake-conflicts-agent && cd intake-conflicts-agent
make install
make run    # the web app on http://localhost:5173, the API on http://127.0.0.1:8000
```

Run an example as Avery Stone, a requester, then switch to Jordan Reyes, an approver, to decide and
open the matter. For a real model, copy `config/.env.example` to `config/.env` and set
`LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` there.

`make dashboard` serves the evaluation dashboard on <http://127.0.0.1:8050>, over the saved runs
in `data/evals/results/`: pick up to three runs and compare their headline numbers, how each kind
of scenario ended, the work each scenario took, and seconds and cost per scenario. `make publish`
writes from the same runs the figures the case study draws, the CSV files for Tableau and the index
the site syncs from; the live workflow runs it after every live evaluation.

## Let Claude play the agent (MCP)

The agent's tools are also an MCP server, so Claude Desktop, Claude Code or any MCP client can do
the agent's work: start a run on an intake email, search every party, draft the matter and send it
for approval. Each call goes through the same toolbox the agent uses, so the same checks hold, and
each is written to the audit log, where the web app's Audit log view shows it.

| Tool | What it does |
| --- | --- |
| `start_intake` | Opens a run on an intake email and returns its id, with the lines that read like orders |
| `search_clients` | Searches the firm's clients for a name (read-only) |
| `search_adverse_parties` | Searches the parties the firm has opposed for a name (read-only) |
| `draft_matter` | Saves the run's draft; every party on it must have been searched in the run, and the findings come from those searches |
| `request_approval` | Sends the run's draft to an approver, which ends the run |
| `end_intake` | Ends a run without sending a draft, saying why |

There is no `open_matter`. The client acts as `[mcp] requester_name`, a requester only, and the
database refuses to open a matter without an approver's record, so a draft it sends waits for an
approver in the web app like any other. The server runs over stdio only, for the person who starts
it: the API's sign-in does not reach it, so it is not served over HTTP. A run the client leaves open
is ended as incomplete when it disconnects. In Claude Desktop's `claude_desktop_config.json`, with
the path to your clone:

```json
{
  "mcpServers": {
    "intake-conflicts-agent": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/intake-conflicts-agent", "--project", "backend",
               "python", "-m", "intake_agent.mcp_server"]
    }
  }
}
```

For Claude Code: `claude mcp add intake-conflicts-agent -- uv run --directory
/path/to/intake-conflicts-agent --project backend python -m intake_agent.mcp_server`.

## Architecture at a glance

![The intake agent at a glance: a browser app calls a local service; only the agent loop talks to the model provider; the agent reads the firm's records and writes only drafts, behind a gate](docs/architecture.svg)

## How it works

![How an intake runs: check the email, read and search, draft, ask for approval, a person decides, open the matter](docs/flow.svg)

1. **Check the email:** 20 to 20,000 characters, at most six intakes a minute per person. A guard
   copies any line that gives the agent orders ("skip the approval step") into the draft, for the
   approver to see.
2. **Read and search:** the model names the prospective client and every party on the other side,
   then calls `search_adverse_parties` for the client (is the firm already against them?) and
   `search_clients` for each other party (does the firm act for them?). Each match comes back with a
   score and a band: exact (the same name once case, punctuation and legal form are set aside),
   likely (92 or more), or possible (80 or more).
3. **Draft:** `draft_matter` is refused until every party on the draft was searched in this run. The
   service computes the findings from those searches, so the agent cannot leave a match out or
   soften one, and the verdict shown is the stricter of the agent's and the checks'.
4. **Ask for approval:** `request_approval` sends this run's own draft, and the agent's work ends.
5. **A person decides:** an approver who is not the requester. Approving past a flagged check needs
   a written reason, such as a waiver on file.
6. **Open the matter:** only with an approval record. The agent runs with the requester's role
   alone, so its `open_matter` calls are always refused, and a SQLite trigger refuses a matter with no
   approval record even if the Python above it were wrong.

| Tool | What it may do |
| --- | --- |
| `search_clients` | Read only, fuzzy matching |
| `search_adverse_parties` | Read only, fuzzy matching |
| `draft_matter` | Write one draft per run, after every party is searched |
| `request_approval` | Send this run's draft to a person; the run ends |
| `open_matter` | Gated: refused without the approver role and an approval record |

The rules for a match, in [`core/conflicts.py`](backend/src/intake_agent/core/conflicts.py):

| Party in the new matter | Matches | Severity |
| --- | --- | --- |
| Other side | A current client, exact or likely | Conflict |
| Other side | A current client, possible | Review: is it the same party? |
| Other side | A former client | Review: is the new matter related? |
| Prospective client | A party in an open matter, exact or likely | Conflict |
| Prospective client | A party in an open matter, possible | Review |
| Prospective client | A party in a closed matter | Review |

## Design

- **Context:** conflicts checks start from intake emails written however people write. Reading them
  and running the searches is slow, careful work, which suits an agent; opening the matter is the step
  with consequences, which does not.
- **Requirements:** read the email; search every party; never skip or soften a match; send ambiguous
  matches to a person; never open a matter without an approval from someone other than the
  requester; record every step; resist instructions in the email; run with no key; measure all of it.
- **Options considered:** a model with every tool and a careful prompt (rejected: the prompt is the
  only control); fixed rules with no model (kept as the offline baseline: brittle on real wording);
  scoped tools with the findings and the gate enforced by the service (chosen); a second model
  reviewing the first one's verdict (deferred: the service already enforces the stricter verdict).
- **Chosen solution:** the model reads and decides what to search; the service validates every tool
  call, computes the findings, shows the stricter verdict, and holds the gate in the API and in SQL.
- **Test plan:** 169 backend and 8 web app tests; a test proving every scenario's expected findings
  hold against the generated database before any model is asked; the 20-scenario evaluation, offline
  in CI and live by hand. Targets set before the first live run: at least 12 of the 13 planted
  records found, no clean scenario shown as a conflict, at least 2 of the 3 ambiguous scenarios marked
  review by the agent, all 6 failure scenarios handled, no matter opened without approval, and
  under $0.10 a scenario. The first live run met every one.
- **Rollout:** local only; a live evaluation reviewed on a branch before it merges; a public demo
  from saved runs. A pilot needs Entra ID sign-in in the web app, the firm's conflicts database
  behind the read-only `Directory` interface, and hosting behind TLS.
- **Unresolved:** a party the agent never names is never searched (the approver sees the email
  beside the draft, and the evaluation measures the parties named); related parties (a parent
  company, an officer) are checked only when the email names them; names are scanned in full on
  every search (fine at 500, not at 500,000); a single approver decides; the per-person limit on
  intakes lives in memory, so two server processes would each allow six a minute; dev sign-in
  trusts headers, so it only listens on this machine.

## Results

**Live**, with `claude-sonnet-5-5` as the agent on GitHub's runner, Oct 29, 2026, all 20 scenarios,
from [live-20261029T144959Z.md](data/evals/results/live-20261029T144959Z.md), beside the offline
baseline from [data/evals/results/offline-latest.md](data/evals/results/offline-latest.md), where
fixed rules play the agent and no model is called:

| Measure | Live | Offline baseline | Target, set before the run |
| --- | --- | --- | --- |
| Conflict recall: planted records the findings include | 100% (13 of 13) | 76.9% (10 of 13) | at least 12 of 13: met |
| False positives: clean scenarios shown as a conflict | 0 of 3 | 0 of 3 | none: met |
| Escalation: ambiguous scenarios the agent itself marked review | 3 of 3 | 1 of 3 | at least 2 of 3: met |
| Verdict shown to the approver matches the expected one | 17 of 17 | 14 of 17 | |
| Failure handling: the timeout, two non-intakes, three injections | 6 of 6 | 5 of 6 | all 6: met |
| Parties named, of those in the emails | 94.9% (37 of 39) | 84.6% | |
| Matters opened without an approval record | 0 | 0 | none: met |
| Times the agent called `open_matter` | 0 | 0 | |
| Median and 95th-percentile time per scenario | 7.9 s, 10.7 s | 0.03 s, 0.12 s | |
| Cost per scenario, and for all 20 | $0.025, $0.49 | $0 | under $0.10: met |

The two parties not named are the timeout scenario's: its searches failed, so nothing was drafted,
as designed. Every drafted scenario named every party. The model found the companies the offline
rules miss, those written without a legal form ("Keystone Medical Supplies", "Pinnacle Foods"),
which is where the baseline lost its three planted records. It marked all three ambiguous scenarios
review rather than deciding them itself.

The dashboard draws these runs, with the offline baseline beside the live run, and
[`data/evals/results/figures.json`](data/evals/results/figures.json) holds the four figures the case
study draws of the latest live runs: how each kind of scenario ended, the model calls and tool calls
each scenario took, seconds per scenario and cost per scenario. The same tables go to Tableau as
CSV files in [`data/export/`](data/export/); [`data/README.md`](data/README.md) describes them.

The three injections were each copied into the draft's warnings for the approver, and none changed
the outcome. Told to skip approval and open the matter, the agent asked for approval and never
called `open_matter`. Told that Pinnacle Foods is not a client and to skip the search, it searched
anyway and found the exact match. Told to list every client, it did not.

This set is now passed in full, so the next step is a harder one: more parties per email, names
spread across a thread, and owners and officers named only by role. The gate held in every
scenario, live and offline, as it must whatever plays the agent.

**Rerun with its trace**, Nov 7, 2026, the same model and 20 scenarios, from
[live-latest.md](data/evals/results/live-latest.md): the same on every measure above, with a median
of 6.7 s and a 95th percentile of 9.3 s per scenario, and $0.49 for all 20. Its trace is kept beside
the results, in [live-20261107T203722Z.spans.jsonl](data/evals/results/live-20261107T203722Z.spans.jsonl):
each scenario's agent run, with its model calls and tool calls.

## Configuration

Every setting, its default and what it does is in [config/README.md](config/README.md). The ones you
are most likely to change:

| Setting | Default | Lives in |
| --- | --- | --- |
| `[llm] provider`, `[llm] model` | `fake`, `claude-sonnet-5-5` | `config/config.toml` |
| `[match] likely`, `[match] possible` | `92`, `80` | `config/config.toml` |
| `[agent] max_steps`, `[agent] run_budget_usd` | `10`, `0.5` | `config/config.toml` |
| `[auth] mode`, `[entra] tenant_id`, `[entra] audience` | `dev`, empty, empty | `config/config.toml` |
| `ANTHROPIC_API_KEY` | unset | `config/.env` only |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | unset: spans stay off | `config/.env` only |

Any setting can be overridden by an environment variable named for its section and key:
`MATCH_LIKELY=90`. The same file also holds the values the service and the web app share, such as
the API's path and the match thresholds; the web app reads the keys it needs from it when it is
built, and never anything from `config/.env`.

## Operating it

- **Logs:** one JSON line per event in `logs/YYYY-MM-DD.jsonl` and on stderr. Email text is never
  logged; contact details and ID-like numbers are redacted from everything that is.
- **Metrics:** each `run.done` line carries the outcome, steps, tool calls, tokens, cost and time;
  each `llm.call` line carries one model call's tokens, latency and cost; `gate.refused` records an
  opening the gate refused, with `role` when it was the agent and `no approval` when an approver or
  a script tried before approving (the evaluation's gate check writes one for each drafted
  scenario).
- **Request id:** on every log line and in the `X-Request-ID` header of every response.
- **Spans:** each intake run is one `invoke_agent intake` span with its outcome, steps, tool calls
  and cost, holding a `chat` span for every model call (tokens, cost, stop reason) and an
  `execute_tool` span for every tool call, which says whether the tool worked and, when the gate
  refused it, the audit code. The names follow the OpenTelemetry GenAI conventions, so Langfuse
  shows the run as an agent with its generations and tools. Set `LANGFUSE_PUBLIC_KEY` and
  `LANGFUSE_SECRET_KEY` in `config/.env` and the spans go to Langfuse; unset, they stay off. Email
  text and tool arguments stay off spans unless `[spans] content` is on, and a log line written in
  a span carries its `trace_id`.
- **Audit log:** the web app's Audit log view, or `GET /api/v1/runs/{id}`: every model call and tool
  call of a run, with redacted arguments and a SHA-256 of each result.
- **When something fails:** `GET /api/v1/health` shows the sign-in mode, the provider and model, and
  the firm's record counts (a 500 there means the database cannot be read). An intake ending
  `failed` names its reason in the audit log: the model unreachable (look for `llm.error`), the
  budget spent, or a limit reached. One ending `incomplete` usually means a conflicts search timed out
  on a locked database: nothing was drafted, so run it again once the lock clears. Bursts of
  `auth.denied` name the check that failed, never the token.

## Testing

```sh
make check   # ruff, mypy (strict), kds-standards, ESLint, Stylelint, Prettier, tsc
make test    # 177 backend and 8 web app tests
make eval    # the offline evaluation, whatever config/.env says; it fails if a matter ever opens
```

Tests never call a model or the network: scripted turns and the offline stand-in take its place.
They write only to temporary folders, run from an empty folder so no `config/.env` leaks in, sign
Entra ID tokens with keys made in the test, and never sleep: retries take an injected wait. The
dashboard's tests draw made-up runs written into each test's own folder. CI runs
the checks, the tests and the offline evaluation on every push to `main` and every pull request,
with the dependency audits, CodeQL and a secrets scan of the whole history. The live evaluation is
started by hand.

## Security

The agent holds the requester's role only and five tools that validate every argument; opening a
matter needs an approval from someone else, checked in the API and again by a database trigger; the
audit records cannot be edited or deleted; Entra ID tokens are checked against the tenant's keys
(RS256 only, issuer, audience, expiry and tenant); dev sign-in and the dashboard, which has no
sign-in, refuse to listen beyond this machine; requests for any other host name are refused. Report
a vulnerability privately as described in [SECURITY.md](SECURITY.md), which also lists every
control.

## Project layout

```text
intake-conflicts-agent/
├── backend/               the service, the evaluation and the dashboard (Python 3.12, uv)
│   ├── src/intake_agent/  config.py, core/ (rules, tools, agent), api/ (FastAPI), mcp_server/, evals/, dashboard/
│   └── tests/             177 tests, offline
├── frontend/              the web app (React, TypeScript, Vite)
│   ├── src/               pages/, components/, lib/, styles/, the API client, config.ts
│   └── tests/             8 tests
├── config/                config.toml: every setting and shared value; .env.example: secret names
├── data/                  samples/ (the planted firm records), evals/ (scenarios, results, figures,
│                          index), export/ (the Tableau CSV files)
├── docs/                  diagrams.toml and the two SVGs it draws
└── .github/               CI, CodeQL, the live evaluation, Dependabot and the workflow that lands its updates
```

## Changelog and license

Changes by release are in [CHANGELOG.md](CHANGELOG.md); this is v0.2.2. Licensed under Apache 2.0
([LICENSE](LICENSE), [NOTICE](NOTICE)).
