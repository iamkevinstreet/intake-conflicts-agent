# Security

## Reporting a vulnerability

Please report it privately, never in a public issue:

- **Preferred:** GitHub's private vulnerability reporting (the repository's **Security** tab, then
  **Report a vulnerability**).
- **Otherwise:** email info@kevindstreet.com with "Security" in the subject.

Include what you found, how to reproduce it, and what an attacker could do with it. You will get an
answer within 3 business days. A confirmed issue is fixed within 30 days, sooner when severe, and you
are credited in the advisory unless you would rather not be.

## Scope

In scope: the service in `backend/`, the web app in `frontend/`, the workflows in `.github/`, and
above all any way to open a matter without an approval record, to approve your own draft, or to
change an audit record.

Out of scope: the model providers' own services, Microsoft Entra ID itself, the made-up scenarios in
`data/evals/` (three contain prompt injections on purpose), dev sign-in on your own machine (it
trusts headers by design and only listens there), and findings that need a compromised developer
machine.

This is a prototype. It is built to the controls below, but it is not hardened for the open internet:
see "Unresolved" in the [README](README.md) before running it anywhere shared.

## How this repository is protected

| Risk | Control |
| --- | --- |
| The agent opens a matter | It acts with the requester's role only; `open_matter` needs the approver role and an approval record; a SQLite trigger refuses a matter without one |
| A person approves their own draft | The API refuses it, and a trigger refuses an approval by the draft's requester |
| A draft changed after approval | The approval stores the draft's SHA-256; a trigger refuses any change to a saved draft's text |
| The agent hides or softens a match | Findings come from the run's own searches, never from the model; the stricter verdict is shown |
| A prompt injection in the email | The email is fenced as data; the guard shows the approver any order-giving line; the gate does not depend on the model |
| A forged or stolen token | RS256 only, checked against the tenant's published keys, with issuer, audience, expiry and tenant required |
| Dev sign-in reachable by others | Settings refuse `[auth] mode = "dev"` on any address but this machine's |
| The dashboard reachable by others | It has no sign-in, so the settings refuse `[dashboard] host` on any address but this machine's |
| DNS rebinding to a local server | Requests addressed to any host name not in `[api] allowed_hosts` are refused |
| An edited audit record | Triggers refuse updates and deletes on runs (once finished), model calls, tool calls, approvals and matters |
| Personal data in logs | Email text is never logged; `kds.logs` redacts emails, phone numbers and ID-like numbers; tool arguments are redacted before they are stored |
| An MCP client acting beyond its role | The MCP server runs over stdio only, for the person who starts it, and acts as a requester; it offers no tool that opens a matter; every call goes through the agent's toolbox, with its checks, and into the audit log; a client may keep only `[mcp] max_open_runs` intakes open |
| Personal data in spans | Spans hold no email text, prompt or tool argument unless `[spans] content` is on; text on a span is redacted as log lines are; a failure is recorded by its type, never its message; spans go only where the Langfuse keys or the standard OpenTelemetry endpoint say |
| Abuse of the model | A per-person limit on intakes, step, tool-call and spending limits per run, a budget per process, and a size limit on every request body (a body that does not declare its length is refused) |
| A committed secret | gitleaks before every commit and over the whole history in CI; secrets live only in `config/.env`, and the settings loader refuses one in `config/config.toml` |
| A vulnerable dependency | Lockfiles with hashes, `pip-audit` and `npm audit` in CI, Dependabot every week, its updates landed only once CI passes |
| A tampered Action or tool | Actions pinned to commit SHAs; the gitleaks download checked against its published SHA-256 |
| A flaw in the code | CodeQL for Python and TypeScript, ruff's security rules (bandit), least-privilege workflow permissions |

