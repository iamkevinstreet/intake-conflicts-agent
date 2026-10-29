# Changelog

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
  each result; the email is kept only as a hash. Triggers make the records append-only.
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
