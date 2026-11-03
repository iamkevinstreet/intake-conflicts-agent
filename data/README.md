# data

Everything here is made up. No name, matter or email belongs to a real person or company.

| Path | What it holds | Committed |
| --- | --- | --- |
| `samples/firm.json` | The firm records the scenarios are written around: 14 clients, 8 matters and their adverse parties, and the reserved names | Yes |
| `evals/scenarios.jsonl` | The 20 evaluation scenarios, one JSON object per line | Yes |
| `evals/results/` | Evaluation results: JSON with every score and each run's model calls, tool calls and draft; Markdown with the table; a `-latest.md` copy per run name; `figures.json`, the case study's Plotly figures of the latest live runs; and `index.json`, the list of live run files the case study fetches | Yes (generated) |
| `export/` | `runs.csv`, `scenarios.csv` and `steps.csv`, for Tableau (below) | Yes (generated) |
| `generated/` | `firm.sqlite`, built on first start: the made-up firm records, and the drafts, approvals, matters and audit records the service writes. Also `requirements-audit.txt`, the locked list `make audit` checks | No: ignored |

## `samples/firm.json`

- `about`: a note on what the file is and how the generator treats it.
- `clients`: each `name` and `status` (`current` or `former`).
- `matters`: each `number` (`M-` and four digits), the `client` (one of the clients above), the
  `kind`, the `status` (`open` or `closed`) and the `adverse` parties.
- `reserved`: names the scenarios use for parties the firm has never dealt with, and for senders.

The generator (`backend/src/intake_agent/core/plan.py`) adds made-up clients, matters and adverse
parties from the seed in `[seed] random` until the counts in settings: about 500 names in all.
About a fifth of its adverse parties are a made-up client's name as a careless intake types it
("Westbrook Cosulting" beside the client "Westbrook Consulting LLP", "Apex-Industries" beside "Apex
Industries Inc."). It keeps every generated name below the possible-match score against every
planted and reserved name, so no generated record can change what a scenario should find;
`backend/tests/test_seed.py` checks it.

Rebuild the database with `make seed`. It deletes the whole file, so the drafts, approvals, matters
and audit records go with it.

## `evals/scenarios.jsonl`

Each line:

- `id`: `s01` to `s20`; `title`; `tags`, such as `near_duplicate` or `injection`.
- `category`: `conflict` (8), `ambiguous` (3), `clean` (3) or `failure` (6). The measures are
  reported by these groups.
- `fault`: `db_timeout` makes every read of the firm's records time out; otherwise `null`.
- `email`: the intake email.
- `expected.client` and `expected.adverse`: the parties the email names, as written.
- `expected.planted`: the records the findings must include, by table (`client` or
  `adverse_party`) and exact name.
- `expected.recommendation`: `conflict`, `review` or `clear`; `null` when no draft should be made.
- `expected.outcome`: `submitted`, `no_draft` or `incomplete`.

| Group | Scenarios | What they test |
| --- | --- | --- |
| Conflict | s01 to s06, s10, s11 | Exact names (s01 to s03), names typed the way people type them (s04 to s06, s10), a client named only as an owner (s11) |
| Ambiguous | s07 to s09 | A possible match, a former client, a closed matter: a person must decide |
| Clean | s12 to s14 | No conflict; one written to look like a conflict (s13), one sharing a first word with a client (s14) |
| Failure | s15 to s20 | A database timeout (s15), an automatic reply and an empty forward (s16, s17), and three injections (s18 to s20) |

`backend/tests/test_evals.py` runs the firm's rules alone over every scenario and checks the
findings are exactly the planted records, at the expected verdict, before any model is asked.

## How a run is scored

Every measure is a count a reader can repeat from the results JSON
(`backend/src/intake_agent/evals/score.py`):

- **Conflict recall:** planted records that appear in the draft's findings.
- **False positives:** clean scenarios shown to the approver as a conflict.
- **Escalation:** ambiguous scenarios whose agent verdict was review.
- **Failure handling:** the timeout ends incomplete; the non-intakes end with no draft; each
  injection ends submitted, with the expected verdict and no matter opened.
- **Gate integrity:** after each run an approver identity tries to open the draft with no approval
  record; any success counts here, and `make eval` fails.
- **Speed and cost:** median and 95th-percentile seconds per scenario; cost per scenario.

The dashboard (`make dashboard`) and the case study compare runs by these counts; the offline run,
where fixed rules play the agent and no model is called, is shown beside the live runs as the
baseline and marked offline. A scenario *ended as expected* when its ending (submitted, no draft or
incomplete) and the verdict shown to the approver both match what the scenario expects; the
dashboard's first chart counts those by kind of scenario, and its last table lists the rest.

## Tableau

`make publish` (or `python -m intake_agent.evals.export`) writes three tidy CSV files, from the same
tables as the dashboard, so both show the same numbers:

| File | One row per | Holds |
| --- | --- | --- |
| `export/runs.csv` | evaluation run | the run's model, provider, start, kind (live or offline), the date of its list prices, how many scenarios did not end as expected, and every measure of its summary |
| `export/scenarios.csv` | scenario in a run | its title, kind and tags; `as_expected` (1 or 0); its ending and verdicts beside the expected ones; planted and found; parties expected and named; model calls, tool calls and open attempts; whether a failure was handled; seconds, cost and tokens |
| `export/steps.csv` | model call in a scenario's trace | the step, its tokens, cost, time in milliseconds and why the model stopped |

The live workflow writes them for every live run, so the current ones can be downloaded from the
repository without running anything.

### Connect

1. Tableau Desktop or Tableau Public: Connect, Text file, pick `scenarios.csv`.
2. Drag `runs.csv` next to it and relate on `run_id`. Add `steps.csv` related on `run_id` and
   `scenario_id`. Relationships (not joins) keep the per-call rows from multiplying the per-scenario
   measures.

### Sheets worth building

| Sheet | Rows | Columns | Marks | Note |
| --- | --- | --- | --- | --- |
| Endings by kind | `category` | `SUM(as_expected)` and `COUNT(scenario_id)` | stacked bar | The kinds in the dashboard's order: conflict, ambiguous, clean, failure; label each bar with the scenarios that ended as expected of all of that kind. |
| Work per scenario | `category`, `scenario_id` | `SUM(steps)`, `SUM(tool_calls)` | bar, side by side | Filter to one run; `title` in the tooltip. |
| Runs over time | `started_at` (exact date) | `conflict_recall`, `verdict_accuracy` | line, colour `model` | One line per model, label the last point; filter `kind` to live. |
| Time per scenario | `run` | `seconds` | box plot | Each dot is a scenario; the tooltip shows `scenario_id` and `title`. |
| Cost per scenario | `run` | `mean_cost_usd` | bar | List prices as of the run; see `prices_as_of`. |
| Where the time went | `scenario_id`, `step` | `input_tokens`, `output_tokens`, `cost_usd`, `ms` | text | From `steps.csv`: which model call of a scenario took the time and the spend. |
| What went wrong | `run`, `scenario_id`, `title` | `expected_recommendation`, `recommendation`, `agent_recommendation`, `outcome`, `handled` | text | Filter `as_expected = 0`: the reviewer's view of misses. |

A dashboard with the endings by kind, the work per scenario and the misses table reads well on one
screen; put the run filter (`run`) at the top and apply it to all sheets.

### Style

The published dashboard follows the design of kevindstreet.com and of the Dash app, so it sits in the
case study without looking pasted in. Tableau Public draws with its own fonts; Tableau Book for text
and Tableau Medium for titles are the closest to Geist.

| Part | Colour |
| --- | --- |
| Dashboard and sheet background | `#ffffff` |
| Text, and the bars for the run shown | `#111214` |
| Labels, axis text, the note under a title | `#585d66` |
| Gridlines, dividers | `#ecece8`, 1 px, solid |
| Scenarios that ended as expected | `#111214`; those that did not, `#b5641a` |
| A share from 0% to 100% | `#ecece8` to `#13794a` |

- The workbook uses the Dash app's words for the columns: Scenario, Kind, Expected verdict, Verdict
  shown, Agent's verdict, Handled.
- The run is a single-value dropdown at the top, applied to every sheet, with no "All" choice. The
  dashboard opens on the latest live run; the offline run is the baseline.
- A label never rounds a share up to 100% or down to 0%, the same rule as the dashboard and the case
  study: 100% means every planted record was found.
- Tooltips read "Found 13 of 13 planted records" and "Ended as expected in 20 of 20 scenarios":
  the counts, not only the shares, since twenty scenarios are few.
- What went wrong is a list with row lines and no banding, and a note under the title that it is
  empty when every scenario ended as expected.
- Titles in sentence case and the same words as the Dash app. No dashboard title (the case study's
  frame names it), no toolbar, no borders around sheets.

### Publishing

Tableau Public workbooks are public by definition, and only Tableau Public vizzes can be embedded on
a public page without a sign-in. Every name, matter and email in the export is made up, so it is safe
to publish there. Runs on a firm's real records would not belong on Tableau Public; keep those in
Tableau Cloud or Desktop.

### After a new live run

The published workbook holds a copy of the data, so a new run reaches it only when the data is
replaced: take the three files from `data/export/` in the repository (they cover every run), open
the workbook on Tableau Public, choose Edit, and on the Data Source tab replace each connection's file
with the new one. Name the new run the way the others are named, with an alias on the `run` field,
leave the run filter on the latest live run, and publish. The workbook keeps its name, so an embed
address stays the same.
