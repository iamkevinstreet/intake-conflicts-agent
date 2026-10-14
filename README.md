# New-matter intake agent with scoped tools and approval gates

An agent reads an intake email, searches clients and adverse parties with read-only tools, writes a draft to
staging, and asks a person to approve. It cannot open a matter. The only code path that opens one checks for an
approval record written by an approver, and the agent has no tool that can write that record.

Case study with the evaluation plan and results: https://kevindstreet.com/projects/intake-conflicts-check-agent/

## Layout

| Path | What it is |
| --- | --- |
| `db.py` | SQLite schema and a seeded, made-up database with near-duplicate names |
| `tools.py` | The five tools, fuzzy matching, the gate, and the audit record for every call |
| `agent.py` | The bounded tool loop |
| `auth.py` | Roles: X-Role header for development; Entra ID validation documented for v0.1 |
| `api.py` | FastAPI service: intake, draft lookup, approver decision, gated open, audit trail |
| `evals/run.py` | Conflict recall, false positives, escalation, approval requested, gate integrity, speed, cost |
| `tests/test_gate.py` | The gate test. If this goes red, nothing ships |

## Run it

```sh
pytest intake_agent/tests
python -m intake_agent.evals.run --cases intake_agent/evals/cases/sample.jsonl --fake
uvicorn intake_agent.api:app --reload
curl -s localhost:8000/intake -H 'content-type: application/json' -H 'X-Role: requester' \
  -d '{"email_text": "We represent Northgate Roofing LLC against Harbor Foods Inc."}'
```

## Human review point

One, and it is mandatory: the approver's decision. The `/drafts/{id}/open` endpoint returns 409 until a decision
of `approved` exists for that draft.

## Changelog

- v0.0, Oct 13, 2026. Scaffold: database, tools with audit, agent loop, role-checked API, gate tests, evaluation.
