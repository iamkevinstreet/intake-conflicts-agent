########################################################################
#                     backend/tests/test_evals.py                      #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           Tests the evaluation: its ground truth against   #
#                     the database, scoring and the runner.            #
########################################################################
"""Tests for the evaluation: its ground truth, its scoring, its runner.

The ground-truth test runs the firm's rules directly, with no agent: for
every scenario, searching each expected party must find exactly the
planted records, at the severity the expected verdict needs. If the
generator or the matcher ever drifted, this fails before any model is
asked anything.
"""

from __future__ import annotations

import pytest
from kds.logs import get_logger

from intake_agent.config import AppSettings
from intake_agent.core.conflicts import findings, search_adverse, search_clients, verdict
from intake_agent.core.firm import SqliteDirectory
from intake_agent.core.store import Store
from intake_agent.evals.run import run_eval, to_markdown
from intake_agent.evals.scenarios import Scenario, load_scenarios

from support import REPO

# Module constants
log = get_logger(__name__)
# log.debug("Loads the scenarios once for the parametrised tests")
SCENARIOS = load_scenarios(REPO / "data/evals/scenarios.jsonl")


# log.debug("Defines the shape test")
def test_twenty_scenarios_in_four_groups() -> None:
    """Twenty scenarios, unique ids, in the four reported groups."""
    # log.debug("Counts each group")
    groups = {
        c: sum(s.category == c for s in SCENARIOS)
        for c in ("conflict", "ambiguous", "clean", "failure")
    }
    # log.debug("Checks the sizes")
    assert (len(SCENARIOS), groups) == (
        20,
        {"conflict": 8, "ambiguous": 3, "clean": 3, "failure": 6},
    )


# log.debug("Defines the ground-truth test, one per scenario")
@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.id for s in SCENARIOS])
def test_ground_truth_holds(scenario: Scenario, store: Store, settings: AppSettings) -> None:
    """The rules alone find the planted records and the verdict."""
    # log.debug("Reads the firm")
    directory = SqliteDirectory(store)
    # log.debug("Takes the thresholds")
    limits = {"likely": settings.match_likely, "possible": settings.match_possible, "limit": 5}
    # log.debug("Searches the client among adverse parties, if there is one")
    found = (
        findings(
            scenario.expected.client,
            "client",
            search_adverse(directory.adverse_parties(), scenario.expected.client, **limits),
        )
        if scenario.expected.client
        else []
    )
    # log.debug("Searches each adverse party among clients")
    for party in scenario.expected.adverse:
        # log.debug("Adds that party's findings")
        found += findings(party, "adverse", search_clients(directory.clients(), party, **limits))
    # log.debug("Checks the findings are exactly the planted records")
    assert sorted((f.match.kind, f.match.name) for f in found) == sorted(
        (p.kind, p.name) for p in scenario.expected.planted
    )
    # log.debug("Checks the verdict, where one is expected")
    if scenario.expected.recommendation is not None:
        # log.debug("Compares it")
        assert verdict(found) == scenario.expected.recommendation


# log.debug("Defines the offline evaluation smoke test")
def test_the_offline_evaluation_runs_and_the_gate_holds(settings: AppSettings) -> None:
    """Four scenarios through the stand-in; no matter opens."""
    # log.debug("Runs a near duplicate, a timeout, a non-intake and an injection")
    results = run_eval(
        settings, name="smoke", only=["s04", "s15", "s16", "s18"], sleep=lambda _: None
    )
    # log.debug("Checks the outcomes and that the gate held")
    assert (
        [s.outcome for s in results.scenarios],
        results.summary["opened_without_approval"],
        "| Conflict recall" in to_markdown(results),
    ) == (["submitted", "incomplete", "no_draft", "submitted"], 0, True)


# log.debug("Defines the failure-handling test")
def test_failure_scenarios_are_handled_by_the_stand_in(settings: AppSettings) -> None:
    """The timeout, both non-intakes, and an injection."""
    # log.debug("Runs them")
    results = run_eval(
        settings, name="smoke", only=["s15", "s16", "s17", "s18"], sleep=lambda _: None
    )
    # log.debug("Checks each was handled")
    assert [s.handled for s in results.scenarios] == [True, True, True, True]


# log.debug("Defines the trace test")
def test_each_scenario_keeps_its_trace(settings: AppSettings) -> None:
    """Each run's calls and draft are saved, without the email."""
    # log.debug("Runs a conflict and a non-intake")
    results = run_eval(settings, name="smoke", only=["s04", "s16"], sleep=lambda _: None)
    # log.debug("Reads the conflict's trace")
    conflict, non_intake = results.traces
    # log.debug("Checks the tools called, the saved draft, and no draft for a non-intake")
    assert (
        [call.tool for call in conflict.detail.tool_calls] if conflict.detail else [],
        conflict.draft is not None and "email" not in conflict.draft,
        non_intake.draft,
    ) == (
        [
            "search_adverse_parties",
            "search_clients",
            "search_clients",
            "draft_matter",
            "request_approval",
        ],
        True,
        None,
    )
