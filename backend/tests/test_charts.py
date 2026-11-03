########################################################################
#                                                                      #
#                     backend/tests/test_charts.py                     #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-03
Last modified on:  2026-11-03

Tests the dashboard's charts, tiles and views: what a comparison of
two runs draws, how the time axis fits the scenarios, how the tiles
write a change, and how the scenarios that did not end as expected
are listed.

Each test writes its own small runs under tmp_path and passes the
folders explicitly, so none depends on the current folder or settings.
"""

########################################################################
#                                                                      #
#                               Imports                                #
#                                                                      #
########################################################################
# Standard library
from __future__ import annotations

import json
from pathlib import Path

# Third-party
from kds.logs import get_logger

# Local
from intake_agent.dashboard.data import frames, load_runs
from intake_agent.dashboard.run_charts import fig_cost, fig_latency
from intake_agent.dashboard.steps_chart import fig_steps
from intake_agent.dashboard.tiles import tile_rows
from intake_agent.dashboard.verdict_chart import fig_verdicts
from intake_agent.dashboard.views import category_order, wrong_rows
from runs import run_at, two_runs, write_run

########################################################################
#                                                                      #
#                           Global constants                           #
#                                                                      #
########################################################################
log = get_logger(__name__)


########################################################################
#                                                                      #
#                         Chart and tile tests                         #
#                                                                      #
########################################################################
# log.debug("Defines the test of a two-run comparison")
def test_comparison_draws_each_run_in_focus_order(tmp_path: Path) -> None:
    """Checks the run in focus comes first in every chart and the key.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
    """
    # log.debug("Builds the tables of both runs")
    runs_df, scenarios_df, _ = frames(load_runs(two_runs(tmp_path)))
    # log.debug("Picks both, newest first: t-2, then t-1")
    ids = list(runs_df["run_id"])
    # log.debug("Draws the chart of endings")
    fig = fig_verdicts(scenarios_df, ids)
    # log.debug("Checks each run has its two segments, the run in focus first")
    assert [trace.meta["role"] for trace in fig.data] == ["run-0", "miss-0", "run-1", "miss-1"]
    # log.debug("Checks the rows name each kind with its count, from the top down")
    assert fig.layout.yaxis.categoryarray == ("Conflict (1)", "Clean (1)", "Failure (1)")
    # log.debug("Checks the later run ended every scenario as expected")
    assert list(fig.data[0].x) == [1, 1, 1]
    # log.debug("Checks the earlier run missed the clean one, and says so at the bar's end")
    assert (list(fig.data[2].x), list(fig.data[3].x)) == ([1, 0, 1], [0, 1, 0])
    # log.debug("Checks the count sits on whichever segment is on top")
    assert (list(fig.data[2].text), list(fig.data[3].text)) == (
        ["1 of 1", "", "1 of 1"],
        ["", "0 of 1", ""],
    )
    # log.debug("Checks the time chart has a row per run, in focus first")
    assert [t.meta["role"] for t in fig_latency(scenarios_df, ids).data] == ["run-0", "run-1"]
    # log.debug("Checks the cost chart has a bar per run, in focus first")
    assert [t.meta["role"] for t in fig_cost(runs_df, ids).data] == ["run-0", "run-1"]
    # log.debug("Checks the cost chart's hover names the list prices' date")
    assert "list prices of 2026-10-15" in fig_cost(runs_df, ids).data[0].hovertemplate


# log.debug("Defines the test of the work chart")
def test_work_chart_draws_the_run_in_focus_by_kind(tmp_path: Path) -> None:
    """Checks the work chart groups the focus run's scenarios by kind.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
    """
    # log.debug("Builds the tables of both runs")
    runs_df, scenarios_df, _ = frames(load_runs(two_runs(tmp_path)))
    # log.debug("Draws the work chart for both; only the run in focus is drawn")
    fig = fig_steps(scenarios_df, list(runs_df["run_id"]))
    # log.debug("Checks the two measures, model calls then tool calls")
    assert [trace.meta["role"] for trace in fig.data] == ["steps", "tool_calls"]
    # log.debug("Checks the rows: the kind on the outer level, the id on the inner")
    assert [list(level) for level in fig.data[0].y] == [
        ["Conflict", "Clean", "Failure"],
        ["s01", "s12", "s16"],
    ]
    # log.debug("Checks the model calls and tool calls of each scenario")
    assert (list(fig.data[0].x), list(fig.data[1].x)) == ([3, 3, 1], [4, 2, 0])
    # log.debug("Checks the hover names the scenario")
    assert fig.data[0].text[0] == "s01  The other side is a current client"
    # log.debug("Checks the chart carries its own key, since the bars are measures")
    assert fig.layout.showlegend is True
    # log.debug("Checks the kinds are listed in the order the results report them")
    assert category_order(scenarios_df) == ["Conflict", "Clean", "Failure"]


# log.debug("Defines the test of the time axis")
def test_time_axis_fits_most_scenarios(tmp_path: Path) -> None:
    """Checks a slow scenario is counted beside its row, not drawn.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
    """
    # log.debug("Makes thirty times between 4 and 5 seconds and one of 16")
    times = [4 + (37 * i % 900) / 1000 for i in range(30)] + [16.0]
    # log.debug("Writes them as a run")
    write_run(tmp_path / "results", "t-1", "2026-10-15T00:00:00+00:00", times, 0.001)
    # log.debug("Builds the tables")
    runs_df, scenarios_df, _ = frames(load_runs(tmp_path / "results"))
    # log.debug("Draws the time chart")
    fig = fig_latency(scenarios_df, list(runs_df["run_id"]))
    # log.debug("Reads the axis range")
    low, high = fig.layout.xaxis.range
    # log.debug("Checks the axis neither starts at zero nor stretches to the slow one")
    assert 3 < low < 4 and high < 8
    # log.debug("Checks the slow one is noted beside the row")
    assert [note.text for note in fig.layout.annotations] == ["1 slower,<br>up to 16.0 s"]
    # log.debug("Checks the slow one's dot is left out, not cut at the edge")
    assert len(fig.data[0].selectedpoints) == 30


# log.debug("Defines the test of the tiles")
def test_tiles_write_each_change_against_the_second_run(tmp_path: Path) -> None:
    """Checks a tile's change has its direction, size and tone.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
    """
    # log.debug("Builds the tables of both runs")
    runs_df, _, _ = frames(load_runs(two_runs(tmp_path)))
    # log.debug("Builds the tiles of the later run against the earlier one")
    tiles = {tile["measure"]: tile for tile in tile_rows(runs_df, ["t-2", "t-1"])}
    # log.debug("Checks planted records found went up fifty points, for the better")
    assert (tiles["conflict_recall"]["value"], tiles["conflict_recall"]["delta"]) == (
        "100%",
        "up 50.0 pts",
    )
    # log.debug("Checks that is for the better")
    assert tiles["conflict_recall"]["good"] is True
    # log.debug("Checks the higher cost is for the worse")
    assert (tiles["mean_cost_usd"]["delta"], tiles["mean_cost_usd"]["good"]) == (
        "up $0.0100",
        False,
    )
    # log.debug("Checks a measure that did not move says so, neither good nor bad")
    assert (tiles["median_seconds"]["delta"], tiles["median_seconds"]["good"]) == (
        "no change",
        None,
    )
    # log.debug("Checks the gate's count is written whole")
    assert tiles["opened_without_approval"]["value"] == "0"
    # log.debug("Checks a lone run has no change on any tile")
    assert {tile["delta"] for tile in tile_rows(runs_df, ["t-2"])} == {None}


# log.debug("Defines the test of the wrong-scenarios table")
def test_wrong_rows_list_scenarios_that_did_not_end_as_expected(tmp_path: Path) -> None:
    """Checks the table holds the misses, in a person's words.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
    """
    # log.debug("Writes two runs")
    results = two_runs(tmp_path)
    # log.debug("Copies the run as a third, started later, where the non-intake got a draft")
    third = run_at("2026-10-15T02:00:00+00:00")
    # log.debug("Gives the non-intake a draft called clear, which no scenario expects")
    third["scenarios"][2] = {
        **third["scenarios"][2],
        "outcome": "submitted",
        "recommendation": "clear",
        "handled": False,
    }
    # log.debug("Writes it")
    (results / "t-3.json").write_text(json.dumps(third), encoding="utf-8")
    # log.debug("Builds the tables")
    runs_df, scenarios_df, _ = frames(load_runs(results))
    # log.debug("Lists the misses of every run")
    rows = wrong_rows(scenarios_df, list(runs_df["run_id"]))
    # log.debug("Checks the three misses, in table order: newest run first")
    assert [(r["run_id"], r["scenario_id"]) for r in rows] == [
        ("t-3", "s12"),
        ("t-3", "s16"),
        ("t-1", "s12"),
    ]
    # log.debug("Checks the non-intake's miss reads as a draft where none was expected")
    assert (rows[1]["expected_recommendation"], rows[1]["recommendation"]) == (
        "no draft",
        "clear",
    )
    # log.debug("Checks it was not handled, and the clean miss has no handled column")
    assert (rows[1]["handled"], rows[0]["handled"]) == ("No", "")
    # log.debug("Checks the planted records found are written of those planted")
    assert rows[0]["found"] == "0 of 0"
