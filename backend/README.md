# backend

The intake service and its evaluation, in Python 3.12, managed with [uv](https://docs.astral.sh/uv/).
Run every command from the repository root, where `config/` and `data/` are.

```sh
make install          # the locked dependencies, hashes checked
make api              # the service on http://127.0.0.1:8000
make check-backend    # ruff, mypy (strict), kds-standards
make test-backend     # 153 tests, offline
make eval             # the 20 scenarios with the offline stand-in
```

## The package

| Path | What it does |
| --- | --- |
| `src/intake_agent/config.py` | Every setting, typed and validated, read from `config/config.toml` and `config/.env`; `SETTINGS`, loaded once, for the values modules share |
| `core/names.py` | Plain forms of names and how alike two are |
| `core/conflicts.py` | The searches and the conflicts rules: severities and verdicts |
| `core/firm.py` | `Directory`: the only, read-only view of the firm the searches get |
| `core/store.py` | The SQLite schema, migrations and the triggers behind the gate and the audit |
| `core/planted.py` | Reads `data/samples/firm.json`: the planted records and reserved names |
| `core/plan.py` | Plans every row of the made-up firm around the planted records, from the seed |
| `core/seed.py` | Writes the plan into an empty database, once |
| `core/models.py` | Tool arguments and replies, matches, findings, drafts and decisions |
| `core/prompt.py` | The agent's rules and its five tools as the model sees them |
| `core/searches.py` | The two search tools, their retries, and what each search found |
| `core/tools.py` | The five tools for one run, with the draft guard and the audit of every call |
| `core/drafts.py` | Drafts, decisions and opening a matter: the gate |
| `core/records.py` | The run, model-call and tool-call records |
| `core/audit.py` | Writes and reads those records |
| `core/agent.py` | The loop, within step, tool-call and budget limits |
| `core/service.py` | One intake end to end; the API and the evaluation both call it |
| `core/guard.py` | Finds order-giving lines in an email for the approver |
| `core/offline.py` | Fixed rules that play the agent with no model |
| `api/` | FastAPI: sign-in (`identity.py`), routes, limits, the app factory |
| `evals/` | The scenarios, the scorers and the runner |

Core logic never imports the web framework, so every rule is tested without HTTP.

## Conventions

- Every file opens with a box that holds its path and a doc block with the dates and a
  description, then its sections: imports, global constants (values from the config), local
  constants and its logic. A logger line sits above every statement; turn the lines on with
  `kds-standards trace on backend` and off before committing.
- Every parameter has a type and a default, `None` where there is no natural one; a function that
  cannot work without a value takes it with `required()` from kds-args. Every function's doc block
  lists each argument and what comes back. No function runs past 60 lines below its doc block and no
  file past 500 lines; `kds-standards check` reports both.
- Tests run in an empty temporary folder, offline, with fresh settings (`tests/conftest.py`);
  shared helpers are in `tests/support.py`.
- Our own packages (`kds-*`) install from the utils repository at one commit, pinned in
  `pyproject.toml`; nothing installs from `main`.
