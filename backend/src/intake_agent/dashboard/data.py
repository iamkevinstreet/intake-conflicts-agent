########################################################################
#                                                                      #
#              backend/src/intake_agent/dashboard/data.py              #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-03
Last modified on:  2026-11-03

Reads the run files into the three tables the dashboard and the
Tableau export share, and names each run. Every run file (a JSON
object with a "scenarios" key) in the results folder is one run: live
when a model played the agent, offline when the stand-in did;
index.json and figures.json sit beside the runs and are skipped. A run
starts when its first scenario does, or, for a run with no trace, at
the time its file name carries. The dashboard and the export
(evals/export.py) read the same tables, so they always agree. The
columns are named in the config's [columns] table.
"""

########################################################################
#                                                                      #
#                               Imports                                #
#                                                                      #
########################################################################
# Standard library
from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

# Third-party
import pandas as pd
from kds.args import required
from kds.logs import get_logger

# Local
from intake_agent.config import SETTINGS

########################################################################
#                                                                      #
#                           Global constants                           #
#                                                                      #
########################################################################
log = get_logger(__name__)
# log.debug("Takes the provider whose runs are the offline baseline, from the config")
OFFLINE_PROVIDER: Final = SETTINGS.eval_offline_provider
# log.debug("Takes the run id column, from the config")
RUN_ID: Final = SETTINGS.columns_run_id
# log.debug("Takes the column of each run's long label, from the config")
RUN: Final = SETTINGS.columns_run
# log.debug("Takes the model column, from the config")
MODEL: Final = SETTINGS.columns_model
# log.debug("Takes the start time column, from the config")
STARTED_AT: Final = SETTINGS.columns_started_at
# log.debug("Takes the scenario id column, from the config")
SCENARIO_ID: Final = SETTINGS.columns_scenario_id
# log.debug("Takes the scenario title column, from the config")
TITLE: Final = SETTINGS.columns_title
# log.debug("Takes the kind of scenario column, from the config")
CATEGORY: Final = SETTINGS.columns_category
# log.debug("Takes the column that is 1 when a scenario ended as expected, from the config")
AS_EXPECTED: Final = SETTINGS.columns_as_expected
# log.debug("Takes the column of each scenario's time, from the config")
SECONDS: Final = SETTINGS.columns_seconds
# log.debug("Takes the column of each scenario's model calls, from the config")
STEPS: Final = SETTINGS.columns_steps
# log.debug("Takes the column of each scenario's tool calls, from the config")
TOOL_CALLS: Final = SETTINGS.columns_tool_calls
# log.debug("Takes the column of the date of a run's list prices, from the config")
PRICES_AS_OF: Final = SETTINGS.columns_prices_as_of
# log.debug("Takes the encoding run files are read in, from the config")
ENCODING: Final = SETTINGS.files_encoding
# log.debug("Takes the name of each kind of scenario, from the config")
CATEGORY_LABELS: Final = SETTINGS.labels_categories

########################################################################
#                                                                      #
#                           Local constants                            #
#                                                                      #
########################################################################
# log.debug("Names the kind of run in which a model played the agent")
LIVE: Final = "live"
# log.debug("Names the kind of run in which the stand-in played the agent")
OFFLINE: Final = "offline"
# log.debug("Names the key only a run file has: its scenarios' scores")
SCENARIOS: Final = "scenarios"
# log.debug("Names the key that holds what the agent did on each scenario")
TRACES: Final = "traces"
# log.debug("Names the key of a trace that holds the run and its calls")
TRACE_DETAIL: Final = "detail"
# log.debug("Names the key of a trace's run record")
TRACE_RUN: Final = "run"
# log.debug("Names the key of a trace that lists the model calls")
MODEL_CALLS: Final = "model_calls"
# log.debug("Names the key of a run's measures")
SUMMARY: Final = "summary"
# log.debug("Names the key and column that say whether a run is live or offline")
KIND: Final = "kind"
# log.debug("Names the key and column of a run's provider")
PROVIDER: Final = "provider"
# log.debug("Names the column of a run's scenarios that did not end as expected")
FAILURES: Final = "failures"
# log.debug("Names the key of a scenario's id in its score and its trace")
ID: Final = "id"
# log.debug("Names the column of a scenario's tags, joined with spaces")
TAGS: Final = "tags"
# log.debug("Names the column of a model call's place in its scenario")
STEP: Final = "step"
# log.debug("Lists the endings and verdicts a scenario's row carries, in column order")
VERDICT_COLUMNS: Final = (
    "outcome",
    "expected_outcome",
    "recommendation",
    "expected_recommendation",
    "agent_recommendation",
    "checks_recommendation",
)
# log.debug("Lists the counts a scenario's row carries, in column order")
COUNT_COLUMNS: Final = ("planted", "found", "parties_expected", "parties_named", "warnings")
# log.debug("Lists the safety and cost measures a scenario's row carries, in column order")
TAIL_COLUMNS: Final = (
    "open_attempts",
    "opened_without_approval",
    "handled",
    "cost_usd",
    "input_tokens",
    "output_tokens",
)
# log.debug("Lists the measures a model call's row carries, in column order")
CALL_COLUMNS: Final = ("input_tokens", "output_tokens", "cost_usd", "ms", "stop_reason")
# log.debug("Sets the form of the time stamp a run file's name ends with, UTC")
STAMP_FORMAT: Final = "%Y%m%dT%H%M%SZ"
# log.debug("Sets how many characters that stamp takes")
STAMP_CHARS: Final = 16
# log.debug("Sets how much of an ISO time a long label keeps: up to the minute")
TO_THE_MINUTE: Final = 16


########################################################################
#                                                                      #
#                              Run tables                              #
#                                                                      #
########################################################################
# log.debug("Defines how the run files are read")
def load_runs(results: Path | None = None) -> list[dict[str, Any]]:
    """Returns every run in the folder, newest first.

    Args:
        results: The folder of run files. Required.

    Returns:
        Each run file's contents, with its file stem as run_id, its
        kind, live or offline, and when it started, sorted by start
        time. A folder that does not exist holds no runs.
    """
    # log.debug("Takes the results folder, which the caller must give")
    results = required(results=results)
    # log.debug("Starts with no runs")
    runs: list[dict[str, Any]] = []
    # log.debug("Reads each JSON file in name order")
    for path in sorted(results.glob("*.json")):
        # log.debug("Parses the file")
        run = json.loads(path.read_text(encoding=ENCODING))
        # log.debug("Skips index.json, figures.json and anything else that is not a run")
        if SCENARIOS not in run:
            # log.debug("Moves to the next file")
            continue
        # log.debug("Names the run after its file")
        run[RUN_ID] = path.stem
        # log.debug("Marks the run live, or offline when the stand-in played the agent")
        run[KIND] = OFFLINE if run[PROVIDER] == OFFLINE_PROVIDER else LIVE
        # log.debug("Dates the run from its first scenario, or its file name")
        run[STARTED_AT] = _started_at(run)
        # log.debug("Keeps the run")
        runs.append(run)
    # log.debug("Puts the newest first; runs that started together keep their order")
    runs.sort(key=lambda run: run[STARTED_AT], reverse=True)
    # log.debug("Returns the runs")
    return runs


# log.debug("Defines which runs a model played the agent in")
def live(runs: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Returns the live runs, in the order given.

    Args:
        runs: Runs as `load_runs` returns them. Required.

    Returns:
        The runs in which a model played the agent; the offline
        baseline is left out.
    """
    # log.debug("Takes the runs, which the caller must give")
    runs = required(runs=runs)
    # log.debug("Returns the runs marked live")
    return [run for run in runs if run[KIND] == LIVE]


# log.debug("Defines the three tidy tables")
def frames(
    runs: list[dict[str, Any]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns a row per run, per scenario, and per model call.

    Args:
        runs: Runs as `load_runs` returns them. Required.

    Returns:
        The runs, scenarios and steps tables, in that order.
    """
    # log.debug("Takes the runs, which the caller must give")
    runs = required(runs=runs)
    # log.debug("Starts the run rows")
    run_rows: list[dict[str, Any]] = []
    # log.debug("Starts the scenario rows")
    scenario_rows: list[dict[str, Any]] = []
    # log.debug("Starts the model-call rows")
    step_rows: list[dict[str, Any]] = []
    # log.debug("Walks the runs")
    for run in runs:
        # log.debug("Labels the run with its model and start, to the minute")
        label = _long_label(run)
        # log.debug("Adds the run's row")
        run_rows.append(_run_row(run, label))
        # log.debug("Adds a row per scenario")
        scenario_rows += [_scenario_row(_head(run, label, s[ID]), s) for s in run[SCENARIOS]]
        # log.debug("Adds a row per model call of each scenario that kept its trace")
        for trace in run[TRACES]:
            # log.debug("Adds the trace's rows, none when the run kept no detail")
            step_rows += _step_rows(_head(run, label, trace[ID]), trace)
    # log.debug("Returns the three tables")
    return pd.DataFrame(run_rows), pd.DataFrame(scenario_rows), pd.DataFrame(step_rows)


# log.debug("Defines the short names of the runs picked")
def run_labels(
    runs_df: pd.DataFrame | None = None, run_ids: Sequence[str] | None = None
) -> dict[str, str]:
    """Returns a short name for each run picked: its start time in UTC.

    The model leads the name when the runs picked mix models, and an
    offline run says so. Ids the table does not hold are left out.

    Args:
        runs_df: The runs table from `frames`. Required.
        run_ids: The runs picked, in order. Required.

    Returns:
        Each run's short name by its id, in the order picked.
    """
    # log.debug("Takes the runs table, which the caller must give")
    runs_df = required(runs_df=runs_df)
    # log.debug("Takes the run ids, which the caller must give")
    run_ids = required(run_ids=run_ids)
    # log.debug("Lists the run ids the table holds")
    known = set(runs_df[RUN_ID])
    # log.debug("Takes the rows of the runs picked, in the order picked")
    picked = runs_df.set_index(RUN_ID).loc[[r for r in run_ids if r in known]]
    # log.debug("Notes whether the runs picked mix models")
    mixed = picked[MODEL].nunique() > 1
    # log.debug("Returns each run's short name by id")
    return {str(run_id): _short_label(row, mixed=mixed) for run_id, row in picked.iterrows()}


# log.debug("Defines when a run started")
def _started_at(run: dict[str, Any] | None = None) -> str:
    """Returns the run's start: its first scenario's, or its file's.

    Args:
        run: A run, named after its file. Required.

    Returns:
        The earliest start among the scenarios that kept their trace,
        as an ISO time; the time the file name carries when none did.
    """
    # log.debug("Takes the run, which the caller must give")
    run = required(run=run)
    # log.debug("Reads when each traced scenario started")
    starts = [
        t[TRACE_DETAIL][TRACE_RUN][STARTED_AT]
        for t in run.get(TRACES, [])
        if t.get(TRACE_DETAIL) is not None
    ]
    # log.debug("Returns the earliest, when any scenario kept its trace")
    if starts:
        # log.debug("Returns it")
        return str(min(starts))
    # log.debug("Reads the stamp the file name ends with, as a time in UTC")
    stamped = datetime.strptime(run[RUN_ID][-STAMP_CHARS:], STAMP_FORMAT).replace(tzinfo=UTC)
    # log.debug("Returns it as an ISO time")
    return stamped.isoformat()


# log.debug("Defines whether a scenario ended as it should have")
def _as_expected(score: dict[str, Any] | None = None) -> bool:
    """Returns whether the ending and the verdict shown both matched.

    Args:
        score: A scenario's score, from the run file. Required.

    Returns:
        True when the run ended as the scenario expected and the
        verdict shown to the approver is the expected one, no draft
        counting as a verdict of its own.
    """
    # log.debug("Takes the score, which the caller must give")
    score = required(score=score)
    # log.debug("Returns whether the ending and the verdict both match")
    return bool(
        score["outcome"] == score["expected_outcome"]
        and score["recommendation"] == score["expected_recommendation"]
    )


# log.debug("Defines a run's long label")
def _long_label(run: dict[str, Any] | None = None) -> str:
    """Returns the model and start time to the minute, offline marked.

    Args:
        run: A run, as `load_runs` marks it. Required.

    Returns:
        The model and the start time to the minute, with offline after
        it for an offline run.
    """
    # log.debug("Takes the run, which the caller must give")
    run = required(run=run)
    # log.debug("Cuts the start time to the minute, with a space for the T")
    stamp = run[STARTED_AT][:TO_THE_MINUTE].replace("T", " ")
    # log.debug("Returns the model and time, marked when the run is an offline run")
    return f"{run[MODEL]} {stamp}" + (f" {OFFLINE}" if run[KIND] == OFFLINE else "")


# log.debug("Defines one run's row")
def _run_row(run: dict[str, Any] | None = None, label: str | None = None) -> dict[str, Any]:
    """Returns the run's row: what, when, how many, and its summary.

    Args:
        run: A run, as `load_runs` marks it. Required.
        label: The run's long label. Required.

    Returns:
        The run's id, label, model, provider, start, kind, the date of
        its list prices, how many scenarios did not end as expected,
        then every measure in its summary.
    """
    # log.debug("Takes the run, which the caller must give")
    run = required(run=run)
    # log.debug("Takes the label, which the caller must give")
    label = required(label=label)
    # log.debug("Returns the row, the summary's measures after the run's own columns")
    return {
        RUN_ID: run[RUN_ID],
        RUN: label,
        MODEL: run[MODEL],
        PROVIDER: run[PROVIDER],
        STARTED_AT: run[STARTED_AT],
        KIND: run[KIND],
        PRICES_AS_OF: run[PRICES_AS_OF],
        FAILURES: sum(not _as_expected(s) for s in run[SCENARIOS]),
        **run[SUMMARY],
    }


# log.debug("Defines the columns a scenario's rows share")
def _head(
    run: dict[str, Any] | None = None,
    label: str | None = None,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    """Returns the run's columns and the scenario's id.

    Args:
        run: The run the scenario is in. Required.
        label: The run's long label. Required.
        scenario_id: The scenario's id. Required.

    Returns:
        The run's id, label and model, and the scenario's id.
    """
    # log.debug("Takes the run, which the caller must give")
    run = required(run=run)
    # log.debug("Takes the label, which the caller must give")
    label = required(label=label)
    # log.debug("Takes the scenario id, which the caller must give")
    scenario_id = required(scenario_id=scenario_id)
    # log.debug("Returns the shared columns")
    return {RUN_ID: run[RUN_ID], RUN: label, MODEL: run[MODEL], SCENARIO_ID: scenario_id}


# log.debug("Defines one scenario's row")
def _scenario_row(
    head: dict[str, Any] | None = None, score: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Returns the scenario's row: what it is, how it ended, its work.

    Args:
        head: The columns the scenario's rows share, from `_head`.
            Required.
        score: The scenario's score, from the run file. Required.

    Returns:
        The shared columns, then the scenario's title, kind and tags,
        whether it ended as expected, its endings and verdicts, its
        counts, its model and tool calls, its safety measures, its
        time, cost and tokens.
    """
    # log.debug("Takes the shared columns, which the caller must give")
    head = required(head=head)
    # log.debug("Takes the score, which the caller must give")
    score = required(score=score)
    # log.debug("Returns the shared columns, then the scenario's own")
    return {
        **head,
        TITLE: score[TITLE],
        CATEGORY: CATEGORY_LABELS.get(score[CATEGORY], score[CATEGORY]),
        TAGS: " ".join(score[TAGS]),
        AS_EXPECTED: int(_as_expected(score)),
        **{name: score.get(name) for name in VERDICT_COLUMNS},
        **{name: score.get(name) for name in COUNT_COLUMNS},
        STEPS: score[STEPS],
        TOOL_CALLS: score[TOOL_CALLS],
        **{name: score.get(name) for name in TAIL_COLUMNS},
        SECONDS: score[SECONDS],
    }


# log.debug("Defines one scenario's model-call rows")
def _step_rows(
    head: dict[str, Any] | None = None, trace: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Returns a row per model call: its tokens, cost, time and stop.

    Args:
        head: The columns the scenario's rows share, from `_head`.
            Required.
        trace: What the agent did on the scenario, from the run file.
            Required.

    Returns:
        One row per model call, in step order; none when the trace
        kept no detail.
    """
    # log.debug("Takes the shared columns, which the caller must give")
    head = required(head=head)
    # log.debug("Takes the trace, which the caller must give")
    trace = required(trace=trace)
    # log.debug("Reads the run and its calls, which a trace without detail lacks")
    detail = trace.get(TRACE_DETAIL) or {}
    # log.debug("Returns a row per model call")
    return [
        {**head, STEP: call[STEP], **{name: call.get(name) for name in CALL_COLUMNS}}
        for call in detail.get(MODEL_CALLS, [])
    ]


# log.debug("Defines one run's short name")
def _short_label(row: pd.Series[Any] | None = None, *, mixed: bool | None = None) -> str:
    """Returns the run's start in UTC, after its model when runs mix.

    Args:
        row: The run's row in the runs table. Required.
        mixed: Whether the runs picked mix models. Required.

    Returns:
        The run's start in UTC, after its model when the runs mix
        models, marked when it is an offline run.
    """
    # log.debug("Takes the row, which the caller must give")
    row = required(row=row)
    # log.debug("Takes whether the runs mix models, which the caller must give")
    mixed = required(mixed=mixed)
    # log.debug("Reads the start time, a trailing Z as UTC")
    when = datetime.fromisoformat(str(row[STARTED_AT]).replace("Z", "+00:00"))
    # log.debug("Writes the month, day, hours and minutes, in UTC")
    label = f"{when.strftime('%b')} {when.day}, {when.strftime('%H:%M')} UTC"
    # log.debug("Puts the model first when the runs picked mix models")
    if mixed:
        # log.debug("Adds the model")
        label = f"{row[MODEL]}, {label}"
    # log.debug("Returns the name, marked when the run is an offline run")
    return label + (f" ({OFFLINE})" if row[KIND] == OFFLINE else "")
