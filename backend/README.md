# backend

The intake service, its evaluation and the evaluation dashboard, in Python 3.12, managed with
[uv](https://docs.astral.sh/uv/). Run every command from the repository root, where `config/` and
`data/` are.

```sh
make install          # the locked dependencies with the dashboard, hashes checked
make api              # the service on http://127.0.0.1:8000
make check-backend    # ruff, mypy (strict), kds-standards
make test-backend     # 169 tests, offline
make eval             # the 20 scenarios with the offline stand-in
make dashboard        # the evaluation dashboard on http://127.0.0.1:8050
make publish          # the figures, the Tableau CSV files and the index, from the saved runs
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
| `core/refusals.py` | The refusals a draft action can meet, and the fingerprint an approval is bound to |
| `core/records.py` | The run, model-call and tool-call records |
| `core/audit.py` | Writes and reads those records |
| `core/agent.py` | The loop, within step, tool-call and budget limits |
| `core/service.py` | One intake end to end; the API and the evaluation both call it |
| `core/guard.py` | Finds order-giving lines in an email for the approver |
| `core/offline.py` | Fixed rules that play the agent with no model |
| `api/` | FastAPI: sign-in (`identity.py`), routes, limits, the app factory |
| `evals/scenarios.py`, `evals/score.py`, `evals/run.py` | The scenarios, the scorers and the runner |
| `evals/shares.py` | How a number and a share are written, by the same rules as the case study |
| `evals/export.py`, `evals/index.py` | The Tableau CSV files and the index the case study reads |
| `dashboard/` | The Dash dashboard over the saved runs, and the Plotly figures the case study draws: `data.py` (run files to tables), `views.py`, `theme.py`, `verdict_chart.py`, `steps_chart.py`, `run_charts.py`, `tiles.py`, `layout.py`, `page.py`, `app.py`, `export.py` |

Core logic never imports the web framework, so every rule is tested without HTTP. The dashboard is
an optional extra (`dash`, `plotly`, `pandas`); `make install` includes it.

## Commands

| Command | What it does |
| --- | --- |
| `python -m intake_agent.api` | Serves the API; it builds the made-up firm database on first start |
| `python -m intake_agent.evals.run --name <name>` | Runs the evaluation; offline with the fake provider, live otherwise; `--only` picks scenarios |
| `python -m intake_agent.dashboard` | Serves the dashboard; `--export-figures` writes the case study's figures instead |
| `python -m intake_agent.evals.export` | Writes the three Tableau CSV files |
| `python -m intake_agent.evals.index` | Writes the index of committed live results |

Run them as `uv run --project backend --no-sync python -m ...`, or through the Makefile.

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
  shared helpers are in `tests/support.py`, and the made-up evaluation runs the dashboard tests
  draw in `tests/runs.py`.
- Our own packages (`kds-*`) install from the utils repository at one commit, pinned in
  `pyproject.toml`; nothing installs from `main`.
