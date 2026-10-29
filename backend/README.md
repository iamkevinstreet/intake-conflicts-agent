# backend

The intake service and its evaluation, in Python 3.12, managed with [uv](https://docs.astral.sh/uv/).
Run every command from the repository root, where `config/` and `data/` are.

```sh
make install          # the locked dependencies, hashes checked
make api              # the service on http://127.0.0.1:8000
make check-backend    # ruff, mypy (strict), kds-standards
make test-backend     # 149 tests, offline
make eval             # the 20 scenarios with the offline stand-in
```

## The package

| Path | What it does |
| --- | --- |
| `intake_agent/config.py` | Every setting, typed and validated, read from `config/settings.toml` and `.env` |
| `core/names.py` | Plain forms of names and how alike two are |
| `core/conflicts.py` | The searches and the conflicts rules: severities and verdicts |
| `core/firm.py` | `Directory`: the only, read-only view of the firm the searches get |
| `core/store.py` | The SQLite schema, migrations and the triggers behind the gate and the audit |
| `core/seed.py` | Builds the made-up firm database around `data/samples/firm.json` |
| `core/models.py` | Tool arguments, matches, findings, drafts and decisions |
| `core/prompt.py` | The agent's rules and its five tools as the model sees them |
| `core/tools.py` | The five tools for one run, with the draft guard and the audit of every call |
| `core/drafts.py` | Drafts, decisions and opening a matter: the gate |
| `core/audit.py` | Run, model-call and tool-call records |
| `core/agent.py` | The loop, within step, tool-call and budget limits |
| `core/service.py` | One intake end to end; the API and the evaluation both call it |
| `core/guard.py` | Finds order-giving lines in an email for the approver |
| `core/offline.py` | Fixed rules that play the agent with no model |
| `api/` | FastAPI: sign-in (`identity.py`), routes, limits, the app factory |
| `evals/` | The scenarios, the scorers and the runner |

Core logic never imports the web framework, so every rule is tested without HTTP.

## Conventions

- Every file carries the header box and a logger line above every statement; turn the
  lines on with `kds-standards trace on backend` and off before committing.
- Tests run in an empty temporary folder, offline, with fresh settings (`tests/conftest.py`);
  shared helpers are in `tests/support.py`.
- Our own packages (`kds-*`) install from the utils repository at one commit, pinned in
  `pyproject.toml`; nothing installs from `main`.
