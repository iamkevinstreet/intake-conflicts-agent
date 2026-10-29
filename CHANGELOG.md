# Changelog

## Unreleased

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
  `kds-standards` keep it that way.
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
