########################################################################
#                                                                      #
#                        backend/tests/runs.py                         #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-03
Last modified on:  2026-11-03

Holds the made-up evaluation runs the dashboard tests draw: a live run
of three scenarios, one of which did not end as expected, and the
helpers that write it, a later run that fixed it, and runs with given
times and costs, into a test's own folder.
"""

########################################################################
#                                                                      #
#                               Imports                                #
#                                                                      #
########################################################################
# Standard library
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

# Third-party
from kds.args import required
from kds.logs import get_logger

########################################################################
#                                                                      #
#                           Global constants                           #
#                                                                      #
########################################################################
log = get_logger(__name__)

########################################################################
#                                                                      #
#                           Local constants                            #
#                                                                      #
########################################################################
# log.debug("Sets when the made-up run started")
STARTED = "2026-10-15T00:00:00+00:00"
# log.debug("Sets a scenario's score as the results file holds it: a conflict found")
SCORE: dict[str, Any] = {
    "id": "s01",
    "title": "The other side is a current client",
    "category": "conflict",
    "tags": ["obvious"],
    "outcome": "submitted",
    "expected_outcome": "submitted",
    "agent_recommendation": "conflict",
    "checks_recommendation": "conflict",
    "recommendation": "conflict",
    "expected_recommendation": "conflict",
    "planted": 1,
    "found": 1,
    "parties_expected": 2,
    "parties_named": 2,
    "warnings": 0,
    "open_attempts": 0,
    "opened_without_approval": False,
    "handled": None,
    "seconds": 2.0,
    "cost_usd": 0.01,
    "input_tokens": 300,
    "output_tokens": 30,
    "steps": 3,
    "tool_calls": 4,
    "run_id": "R-0000000001",
}
# log.debug("Sets one model call of a trace")
CALL: dict[str, Any] = {
    "step": 1,
    "input_tokens": 100,
    "output_tokens": 10,
    "cost_usd": 0.003,
    "ms": 500,
    "stop_reason": "tool_use",
}
# log.debug("Sets a live run of three scenarios; the clean one is wrongly sent to review")
RUN: dict[str, Any] = {
    "name": "t",
    "model": "test-model",
    "provider": "anthropic",
    "prices_as_of": "2026-10-15",
    "summary": {
        "scenarios": 3,
        "conflict_recall": 0.5,
        "false_positive_rate": 0.0,
        "clean_flagged_for_review": 1.0,
        "escalation": None,
        "verdict_accuracy": 0.5,
        "agent_verdict_accuracy": 0.5,
        "failure_handling": 1.0,
        "parties_named": 1.0,
        "opened_without_approval": 0,
        "open_attempts": 0,
        "median_seconds": 2.0,
        "p95_seconds": 3.0,
        "mean_cost_usd": 0.01,
        "total_cost_usd": 0.03,
    },
    "scenarios": [
        SCORE,
        {
            **SCORE,
            "id": "s12",
            "title": "A plain intake with no conflict",
            "category": "clean",
            "tags": ["clean"],
            "agent_recommendation": "review",
            "checks_recommendation": "clear",
            "recommendation": "review",
            "expected_recommendation": "clear",
            "planted": 0,
            "found": 0,
            "seconds": 3.0,
            "cost_usd": 0.012,
            "tool_calls": 2,
        },
        {
            **SCORE,
            "id": "s16",
            "title": "Not an intake: an automatic reply",
            "category": "failure",
            "tags": ["malformed"],
            "outcome": "no_draft",
            "expected_outcome": "no_draft",
            "agent_recommendation": None,
            "checks_recommendation": None,
            "recommendation": None,
            "expected_recommendation": None,
            "planted": 0,
            "found": 0,
            "parties_expected": 0,
            "parties_named": 0,
            "handled": True,
            "seconds": 1.0,
            "cost_usd": 0.004,
            "steps": 1,
            "tool_calls": 0,
        },
    ],
    "traces": [
        {
            "id": scenario_id,
            "detail": {
                "run": {"id": "R-0000000001", "started_at": STARTED},
                "model_calls": [{**CALL, "step": step} for step in range(1, steps + 1)],
                "tool_calls": [],
            },
            "draft": None,
            "text": "",
        }
        for scenario_id, steps in (("s01", 3), ("s12", 3), ("s16", 1))
    ],
}


########################################################################
#                                                                      #
#                             Made-up runs                             #
#                                                                      #
########################################################################
# log.debug("Defines a made-up run that started at a given time")
def run_at(started: str | None = None, **changes: Any) -> dict[str, Any]:
    """Returns a copy of RUN started at `started`, with any changes.

    Args:
        started: When the run's scenarios started, as an ISO time.
            Required.
        **changes: Top-level keys of the run to replace.

    Returns:
        The run, every trace started at the time given.
    """
    # log.debug("Takes the start time, which the caller must give")
    started = required(started=started)
    # log.debug("Copies the run, with the changes")
    run = {**copy.deepcopy(RUN), **changes}
    # log.debug("Starts every trace at the time given")
    for trace in run["traces"]:
        # log.debug("Sets the trace's start")
        trace["detail"]["run"]["started_at"] = started
    # log.debug("Returns the run")
    return run


# log.debug("Defines a results folder holding the one run")
def one_run(tmp_path: Path | None = None) -> Path:
    """Writes RUN as the only run, and returns the results folder.

    Args:
        tmp_path: The test's temporary folder. Required.

    Returns:
        The results folder.
    """
    # log.debug("Takes the test's folder, which the caller must give")
    tmp_path = required(tmp_path=tmp_path)
    # log.debug("Makes the results folder")
    results = tmp_path / "results"
    # log.debug("Creates it")
    results.mkdir()
    # log.debug("Writes the run")
    (results / "t-1.json").write_text(json.dumps(RUN), encoding="utf-8")
    # log.debug("Returns the folder")
    return results


# log.debug("Defines a results folder holding two runs an hour apart")
def two_runs(tmp_path: Path | None = None) -> Path:
    """Writes RUN and a later run that gets every verdict right, dearer.

    The later run, an hour after, calls the clean scenario clear.

    Args:
        tmp_path: The test's temporary folder. Required.

    Returns:
        The results folder, holding both runs.
    """
    # log.debug("Takes the test's folder, which the caller must give")
    tmp_path = required(tmp_path=tmp_path)
    # log.debug("Copies the run, started an hour later")
    later = run_at("2026-10-15T01:00:00+00:00")
    # log.debug("Gives it every verdict right and a higher cost")
    later["summary"] = {
        **RUN["summary"],
        "conflict_recall": 1.0,
        "clean_flagged_for_review": 0.0,
        "verdict_accuracy": 1.0,
        "mean_cost_usd": 0.02,
    }
    # log.debug("Calls the clean scenario clear, and shows that verdict to the approver")
    later["scenarios"][1] = {
        **later["scenarios"][1],
        "agent_recommendation": "clear",
        "recommendation": "clear",
    }
    # log.debug("Writes the earlier run")
    results = one_run(tmp_path)
    # log.debug("Writes the later run")
    (results / "t-2.json").write_text(json.dumps(later), encoding="utf-8")
    # log.debug("Returns the folder")
    return results


# log.debug("Defines a run of scenarios that all ended as expected, with given times")
def write_run(
    results: Path | None = None,
    name: str | None = None,
    started: str | None = None,
    seconds: list[float] | None = None,
    cost: float | None = None,
) -> None:
    """Writes a run with the given times and one cost per scenario.

    Args:
        results: The results folder, made if need be. Required.
        name: The run file's name, without .json. Required.
        started: When the run started, as an ISO time. Required.
        seconds: Each scenario's time, in seconds. Required.
        cost: Every scenario's cost, in dollars. Required.
    """
    # log.debug("Takes the results folder, which the caller must give")
    results = required(results=results)
    # log.debug("Takes the run's name, which the caller must give")
    name = required(name=name)
    # log.debug("Takes the start time, which the caller must give")
    started = required(started=started)
    # log.debug("Takes the times, which the caller must give")
    seconds = required(seconds=seconds)
    # log.debug("Takes the cost, which the caller must give")
    cost = required(cost=cost)
    # log.debug("Copies the run, started at the time given")
    run = run_at(started)
    # log.debug("Makes one scenario per time, each the conflict scenario that ended right")
    run["scenarios"] = [
        {**SCORE, "id": f"s{i + 1:02d}", "seconds": s, "cost_usd": cost}
        for i, s in enumerate(seconds)
    ]
    # log.debug("Keeps one trace, so the run still has its start")
    run["traces"] = run["traces"][:1]
    # log.debug("Writes the summary to match")
    run["summary"] = {
        **RUN["summary"],
        "scenarios": len(seconds),
        "conflict_recall": 1.0,
        "median_seconds": sorted(seconds)[len(seconds) // 2],
        "mean_cost_usd": cost,
    }
    # log.debug("Makes the results folder if it is not there yet")
    results.mkdir(exist_ok=True)
    # log.debug("Writes the run")
    (results / f"{name}.json").write_text(json.dumps(run), encoding="utf-8")
