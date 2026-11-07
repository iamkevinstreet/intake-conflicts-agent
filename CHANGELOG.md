# Changelog

## Unreleased

- **Dependency updates land by themselves.** Dependabot groups each week's updates into one pull
  request per kind (Actions, the backend, the frontend), and the new `dependency-updates` workflow
  lands them every weekday: it applies the oldest open one to `main` as an ordinary commit, refreshes
  the dates in the headers it changes, runs the whole of CI on that commit, and moves `main` to it only
  when every check passes. One whose checks fail is labelled "needs a person" and waits. CI can now
  be called for a given commit, which is how the workflow checks one before it lands.

## v0.4.0, Nov 7, 2026

- **An MCP server:** Claude Desktop, Claude Code or any MCP client can play the agent over stdio:
  `start_intake`, `search_clients`, `search_adverse_parties`, `draft_matter`, `request_approval`
  and `end_intake`, built on the MCP Python SDK 2.3. Every call goes through the agent's own
  toolbox, so a draft names only parties searched in its run and its findings come from those
  searches, and every call is written to the audit log. There is no `open_matter`: the client acts
  as a requester only (`[mcp] requester_id` and `requester_name`), and the database refuses to
  open a matter without an approver's record. A client may keep `[mcp] max_open_runs` intakes
  open, and a run left open ends as incomplete when the client disconnects. Six tests drive the
  server through a real MCP client.
- **Shared pieces:** the database and its views open in one place, `open_records()`, for the API
  and the MCP server alike, and the email's length check is `check_email()`. The outcome name
  `incomplete` moves to `config.py`, where both use it.
- 177 backend tests. The health report and the API schema say 0.4.0.

## v0.3.1, Nov 7, 2026

- **Spans:** the Anthropic SDK no longer adds a span of its own to each model call. That span
  repeated the `chat` span's call, tokens included, so Langfuse listed every call twice, and it
  carried the account's organization and workspace ids. The workbench moves to utils v0.6.1, which
  builds the Anthropic client with the SDK's spans and trace headers off. The spans file of the
  Nov 7 live run, on the eval-results branch, has those spans removed too.
- 171 backend tests. The health report and the API schema say 0.3.1.

## v0.3.0, Nov 7, 2026

- **Spans:** each intake run is one `invoke_agent intake` span recording its outcome, steps, tool
  calls and cost, and holding a `chat` span for every model call and an `execute_tool` span for
  every tool call, which records whether the tool worked and, when it did not, the audit code: the
  gate's refusal of `open_matter` shows there. The names follow the OpenTelemetry GenAI conventions,
  so Langfuse shows a run as an agent with its generations and tools. Each evaluation scenario runs
  in its own `eval` span with its scores, and a run's scenarios share one session. With
  `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` in `config/.env` the spans go to Langfuse; unset,
  they stay off. The live workflow sends them when those two repository secrets are set and keeps
  each run's spans beside its results. Two tests check the tree and the gate's refusal.
- **The workbench:** utils v0.6.0 (spans), pinned at its new commit. The new settings, `[spans]`
  and `[langfuse]`, are in `config/config.toml`.
- 171 backend tests. The health report and the API schema say 0.3.0.

## v0.2.2, Nov 5, 2026

- **Dependencies:** the web app moves to ESLint 10.14.0, eslint-plugin-jsdoc 65.4.2 and globals
  17.14.0. The plugin is two major versions on, with the same rules. Nothing had to change: lint,
  the types, the tests, the build and the audits pass as they were. The health report and the API
  schema say 0.2.2.

## v0.2.1, Nov 5, 2026

- **Dashboard:** `make dashboard` serves a Plotly Dash dashboard over the saved runs, in the design
  of kevindstreet.com (Geist, light and dark): pick up to three runs, the first in focus, and see
  seven headline numbers and how each moved against the second run, how each kind of scenario ended
  (as expected or not, stacked, with the count of scenarios in each kind), the model calls and tool
  calls each scenario took, seconds per scenario as a dot per scenario over each run's box, cost
  per scenario at list prices, every run's summary, and the scenarios that did not end as expected.
  The offline run, where fixed rules play the agent, is shown beside the live runs as the baseline
  and marked offline. The dashboard has no sign-in, so the settings refuse any address but this
  machine's.
- **Figures and exports:** `make publish` writes `data/evals/results/figures.json`, the four
  figures of the latest three live runs as Plotly JSON, each trace naming its part in `meta.role`
  so the case study can draw them in its own palette; `data/export/runs.csv`, `scenarios.csv` and
  `steps.csv`, tidy files for Tableau from the same tables as the dashboard; and
  `data/evals/results/index.json`, the live run files, newest first, and the figures file, which
  the site syncs from. The live workflow runs it after every live evaluation and commits the three
  with the results. `data/README.md` describes the files and the Tableau sheets to build from
  them.
- **Settings:** `config/config.toml` gains the dashboard's address and part ids, the tables' column
  names, the charts' settings and titles, the name of each kind of scenario, where the CSV files
  and the figures go, the encoding every file is written in and the provider that marks a run
  offline; the dashboard is an optional extra (`dash`, `plotly`, `pandas`) that `make install`
  includes. The service, the API and the evaluation's numbers are unchanged.
- 169 backend tests (15 of them the dashboard's) and 8 web app tests, all offline.
- **The box:** every file's header box and every section banner is five lines now: a border, a
  blank walled line, the title, another blank walled line and a border. The shared packages are
  pinned to utils v0.5.0, commit `fcac0477e1caadccf1e2d7580ce648258c5a79fa`, whose checker asks for
  that form and whose `stamp` brought every file to it. The dotfiles that take `#` comments carry
  a header like the Makefile. No code changed.
- **Utils v0.5.1:** the shared packages then move to utils v0.5.1, commit
  `e57de0e97d1c41616af1a98873f6beeecc74c99f`, whose checker also reads the statements inside a
  function whose signature wraps and inside a bare `catch`. Each of them in the web app already
  had its logger line, so no code changed; the health report and the API schema say 0.2.1.

## v0.2.0, Oct 29, 2026

The code moves to the updated code standard: a new place for the package and the settings, and a new
layout for every file. The API, the evaluation's numbers and the published results stay the same,
and so do the 153 backend and 8 web app tests. The release also carries the first live results and
the fixes made after v0.1.0.

- **src layout:** the package lives in `backend/src/intake_agent`, so the tests import the installed
  package, as anyone else would.
- **Settings:** `config/config.toml` (was `config/settings.toml`) holds every setting and every
  value two files share: the API's path, the request id header, the list limits, the id patterns,
  and the role and verdict names. Secrets go in `config/.env`, listed in `config/.env.example` (was
  `.env.example`). The web app reads the keys it needs from the same file when it is built, and
  nothing from `config/.env`; so does the dev server's proxy, for the API's path and address.
  `frontend/src/config.ts` holds only those settings now, and the people a developer can act as
  moved to `frontend/src/personas.ts`.
- **File layout:** every file opens with a box that holds its path and a doc block with the dates
  and a description, then its imports in three labelled groups, its global constants (the values it
  takes from the config), its local constants and its logic, each under a banner. Three modules that
  passed 500 lines were split by job: the seed into the planted records (`core/planted.py`), the
  plan (`core/plan.py`) and the seed itself; the audit into its records (`core/records.py`) and the
  log; the tools into the searches (`core/searches.py`) and the toolbox.
- **Functions:** every parameter has a type and a default, `None` or `null` where there is no
  natural one. A function that cannot work without a value takes it with `required()` (from
  kds-args, and `frontend/src/lib/required.ts` in the web app), which names the argument a caller
  left out. Every function's doc block lists each argument and what comes back, and no function runs
  past 60 lines below it: the web app's three pages, its shell and the intake form were split into
  hooks and smaller components, and render exactly as before. ruff's annotation rules, ESLint's doc
  block rules, explicit return types, `kds/param-defaults`, `max-lines-per-function` and
  `kds-standards` keep it that way. The API schema still describes each route by its summary
  alone: the Args and Returns sections are for readers of the code.
- **Utils:** every `kds-*` package pins utils v0.4.2 (`62a38c5a3ecf667e3e227b18412abd77759c38d5`),
  and kds-args joins them. With it, the first retry after a provider error waits up to half a
  second, not a whole one, and a missing key's message points at `config/.env`.
- **Live results:** with `claude-sonnet-5-5` as the agent on all 20 scenarios, every planted record
  was found (13 of 13), no clean scenario was shown as a conflict, all 3 ambiguous scenarios were
  marked review, all 6 failures were handled, and no matter was opened, at $0.025 a scenario. Every
  target set before the run was met.
- **Outages:** a provider failure that outlasts the retries now ends the run with "the model could
  not be reached", recognised by kind, instead of as an unplanned error.
- **Edge:** a request body that does not declare its length is refused (411) rather than read
  unmeasured; every reply, including a refused host name and an unplanned error, carries the
  request id and the security headers; an unplanned error is a plain 500.
- **Notes:** `[api] max_note_chars` now limits a decision note in the API, and the web app reads
  its limit from its config.
- **Evaluation:** `make eval` runs the offline stand-in whatever `config/.env` says, so its
  results are always the offline baseline.

## v0.1.0, Oct 29, 2026

A rebuild to one code standard, with the gate held in three places and an evaluation you can
repeat.

- **Firm data:** about 500 made-up names (300 clients, 200 adverse parties, 180 matters), built from
  a seed around the records the scenarios plant in `data/samples/firm.json`. Dozens of adverse
  parties are typed variants of clients. No generated name comes within the possible-match score of
  a planted or reserved one, and a test proves it.
- **Matching:** names are compared in a plain form (case, punctuation, a leading "the" and legal forms
  set aside), as the best of three scores, in three bands: exact, likely (92 or more) and possible (80
  or more). Every near duplicate the synthetic data makes of 200 companies scores at least possible.
- **Tools:** the five tools validate their arguments against the same models that give the model its
  schemas. `draft_matter` is refused until every party was searched, and its findings come from the
  run's own searches, so the agent can neither skip nor soften a match. The approver sees the
  stricter of the agent's verdict and the checks'.
- **Gate:** opening a matter needs the approver role and an approval record from someone other than
  the requester, checked by the API and again by SQLite triggers. The agent acts with the requester's
  role only. Approving past a flagged check needs a written reason. Drafts are hashed, and the
  approval is bound to the hash.
- **Audit:** one record per run and per model and tool call, with redacted arguments and a SHA-256 of
  each result; the audit keeps the email only as a hash, and the draft keeps its text for the
  approver. Triggers make the records append-only.
- **Identity:** Microsoft Entra ID access tokens checked in the API against the tenant's signing keys
  (RS256 only; issuer, audience, expiry, tenant), with app roles mapped to requester and approver.
  Dev sign-in trusts headers and refuses to listen beyond this machine. The scaffold's stub, which
  refused every token, is gone.
- **Web app:** React and TypeScript. Run an intake and see every step; review a draft with its
  findings, decide, and open the matter; read the audit log.
- **Evaluation:** 20 scenarios: 8 conflicts (obvious, near duplicates, people), 3 ambiguous, 3 clean
  (one written to look like a conflict), and 6 failures: a database timeout, two non-intakes and three
  injections. Scored by fixed checks, offline in CI and live by hand. Each run's model calls,
  tool calls and draft are saved with the results.
- **Repository:** strict mypy, ESLint and Stylelint, lockfiles with hashes, `pip-audit` and
  `npm audit`, CodeQL, Dependabot, Actions pinned to commit SHAs, `SECURITY.md`, and diagrams drawn
  from `docs/diagrams.toml`. Shared packages pin utils v0.3.0, which sends a turn's tool results to
  Claude together.

## v0.0, Oct 13, 2026

Scaffold: database, tools with audit, agent loop, role-checked API, gate tests, and an evaluation
entry point. Shared utilities came from [utils](https://github.com/iamkevinstreet/utils).
