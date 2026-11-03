########################################################################
#                                                                      #
#                   backend/tests/test_dashboard.py                    #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-03
Last modified on:  2026-11-03

Tests the dashboard's tables, the Tableau and figures exports, the
index, the command line and the app. The charts and tiles have their
own tests.

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
import pytest
from kds.logs import get_logger

# Local
from intake_agent.config import get_app_settings
from intake_agent.dashboard.__main__ import main
from intake_agent.dashboard.app import build_app
from intake_agent.dashboard.data import frames, live, load_runs, run_labels
from intake_agent.dashboard.export import export_figures
from intake_agent.dashboard.steps_chart import fig_steps
from intake_agent.dashboard.verdict_chart import fig_verdicts
from intake_agent.evals.export import export
from intake_agent.evals.index import build_index
from runs import RUN, one_run, run_at, two_runs

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
# log.debug("Matches Dash 4's warning that its tables will move to a separate package")
TABLE_DEPRECATED = r"ignore:\s*The dash_table.DataTable will be removed:DeprecationWarning"


########################################################################
#                                                                      #
#                           Dashboard tests                            #
#                                                                      #
########################################################################
# log.debug("Defines the test of the tables and the single-run charts")
def test_frames_and_figures(tmp_path: Path) -> None:
    """Checks one run makes a run row, three scenarios and seven calls.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
    """
    # log.debug("Builds the tables")
    runs_df, scenarios_df, steps_df = frames(load_runs(one_run(tmp_path)))
    # log.debug("Checks the row counts")
    assert [len(runs_df), len(scenarios_df), len(steps_df)] == [1, 3, 7]
    # log.debug("Checks the run started when its first scenario did, and is live")
    assert runs_df[["started_at", "kind", "failures"]].iloc[0].tolist() == [
        "2026-10-15T00:00:00+00:00",
        "live",
        1,
    ]
    # log.debug("Checks the kinds of scenario are named, and which ended as expected")
    assert scenarios_df["category"].tolist() == ["Conflict", "Clean", "Failure"]
    # log.debug("Checks the clean scenario, sent to review, is the one that did not")
    assert scenarios_df["as_expected"].tolist() == [1, 0, 1]
    # log.debug("Checks the model calls carry their scenario and step")
    assert steps_df.groupby("scenario_id")["step"].max().to_dict() == {
        "s01": 3,
        "s12": 3,
        "s16": 1,
    }
    # log.debug("Checks the chart of endings draws one run: its two segments")
    assert len(fig_verdicts(scenarios_df, list(runs_df["run_id"])).data) == 2
    # log.debug("Checks the work chart takes a single run id")
    assert len(fig_steps(scenarios_df, str(runs_df["run_id"].iloc[0])).data) == 2


# log.debug("Defines the test of the Tableau export")
def test_export_writes_three_csvs(tmp_path: Path) -> None:
    """Checks the export writes runs, scenarios and steps as CSV.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
    """
    # log.debug("Exports the run")
    written = export(one_run(tmp_path), tmp_path / "out")
    # log.debug("Checks the three files, in order")
    assert [p.name for p in written] == ["runs.csv", "scenarios.csv", "steps.csv"]
    # log.debug("Reads the scenarios file")
    scenarios = (tmp_path / "out" / "scenarios.csv").read_text(encoding="utf-8").splitlines()
    # log.debug("Checks it has a header and three rows")
    assert len(scenarios) == 4
    # log.debug("Checks the columns the brief asks for are there, in plain words")
    assert {"scenario_id", "title", "category", "as_expected", "steps", "tool_calls"} <= set(
        scenarios[0].split(",")
    )
    # log.debug("Reads the runs file's header")
    runs = (tmp_path / "out" / "runs.csv").read_text(encoding="utf-8").splitlines()[0]
    # log.debug("Checks the run's own columns come before every summary measure")
    assert runs.startswith("run_id,run,model,provider,started_at,kind,prices_as_of,failures,")
    # log.debug("Checks the steps file has a header and seven rows")
    assert (tmp_path / "out" / "steps.csv").read_text(encoding="utf-8").count("\n") == 8


# log.debug("Defines the test of the parts the case study restyles")
def test_export_figures_carries_roles(tmp_path: Path) -> None:
    """Checks each trace says its part, for the case study to restyle.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
    """
    # log.debug("Exports the figures of both runs")
    payload = export_figures(two_runs(tmp_path), tmp_path / "figures.json")
    # log.debug("Checks the four figures, in order")
    assert [f["name"] for f in payload["figures"]] == ["verdicts", "steps", "latency", "cost"]
    # log.debug("Checks the latest run heads the file")
    assert [payload["run_id"], payload["model"]] == ["t-2", "test-model"]
    # log.debug("Checks the runs, newest first, with their short names")
    assert payload["runs"] == [
        {"run_id": "t-2", "label": "Oct 15, 01:00 UTC"},
        {"run_id": "t-1", "label": "Oct 15, 00:00 UTC"},
    ]
    # log.debug("Checks every trace has a part")
    assert all(trace["meta"]["role"] for f in payload["figures"] for trace in f["spec"]["data"])
    # log.debug("Checks each figure carries its title")
    assert [f["spec"]["layout"]["title"]["text"] for f in payload["figures"]] == [
        f["title"] for f in payload["figures"]
    ]


# log.debug("Defines the test that the export keeps the latest three runs")
def test_export_figures_keeps_three_runs(tmp_path: Path) -> None:
    """Checks the figures draw up to three runs, newest first.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
    """
    # log.debug("Writes two runs")
    results = two_runs(tmp_path)
    # log.debug("Writes a third, started last")
    (results / "t-3.json").write_text(
        json.dumps(run_at("2026-10-15T02:00:00+00:00")), encoding="utf-8"
    )
    # log.debug("Exports the figures")
    payload = export_figures(results, tmp_path / "figures.json")
    # log.debug("Checks the three runs, newest first")
    assert [r["run_id"] for r in payload["runs"]] == ["t-3", "t-2", "t-1"]
    # log.debug("Lists the parts of the chart of endings' traces")
    roles = {trace["meta"]["role"] for trace in payload["figures"][0]["spec"]["data"]}
    # log.debug("Checks each run has its part, with its scenarios that did not end as expected")
    assert roles == {"run-0", "run-1", "run-2", "miss-0", "miss-1", "miss-2"}


# log.debug("Defines the test that the export needs live runs")
def test_export_figures_needs_live_runs(tmp_path: Path) -> None:
    """Checks an empty folder is refused, saying what to do.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
    """
    # log.debug("Exports from a folder that does not exist")
    with pytest.raises(FileNotFoundError, match="no live runs"):
        # log.debug("Tries the export")
        export_figures(tmp_path / "nowhere", tmp_path / "figures.json")


# log.debug("Defines the test of the offline baseline")
def test_offline_runs_are_marked_and_left_out_of_the_figures(tmp_path: Path) -> None:
    """Checks the stand-in's runs are offline: shown, but not drawn.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
    """
    # log.debug("Writes the live run")
    results = one_run(tmp_path)
    # log.debug("Writes an index beside it, which is not a run")
    (results / "index.json").write_text(json.dumps({"runs": ["t-1.json"]}), encoding="utf-8")
    # log.debug("Writes an offline run a day later")
    (results / "o-1.json").write_text(
        json.dumps(run_at("2026-10-16T00:00:00+00:00", provider="fake", model="fake-model")),
        encoding="utf-8",
    )
    # log.debug("Reads the folder")
    runs = load_runs(results)
    # log.debug("Checks both runs, newest first, each with its kind")
    assert [(r["run_id"], r["kind"]) for r in runs] == [("o-1", "offline"), ("t-1", "live")]
    # log.debug("Checks only the live run is drawn")
    assert [r["run_id"] for r in live(runs)] == ["t-1"]
    # log.debug("Checks the short names mark the offline run, the model first as they mix")
    assert run_labels(frames(runs)[0], ["o-1", "t-1"]) == {
        "o-1": "fake-model, Oct 16, 00:00 UTC (offline)",
        "t-1": "test-model, Oct 15, 00:00 UTC",
    }
    # log.debug("Checks the figures draw the live run alone")
    assert [r["run_id"] for r in export_figures(results, tmp_path / "f.json")["runs"]] == ["t-1"]


# log.debug("Defines the test of the index")
def test_index_lists_live_runs_newest_first(tmp_path: Path) -> None:
    """Checks the index names the live run files and the figures.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
    """
    # log.debug("Writes two live runs")
    results = two_runs(tmp_path)
    # log.debug("Writes an offline run between them")
    (results / "o-1.json").write_text(
        json.dumps(run_at("2026-10-15T00:30:00+00:00", provider="fake")), encoding="utf-8"
    )
    # log.debug("Checks the index lists the live runs, newest first, and no figures yet")
    assert build_index(results) == {"runs": ["t-2.json", "t-1.json"], "figures": None}
    # log.debug("Writes the figures")
    export_figures(results, results / "figures.json")
    # log.debug("Checks the index names them now, and still only the runs")
    assert build_index(results) == {"runs": ["t-2.json", "t-1.json"], "figures": "figures.json"}


# log.debug("Defines the test of a run that kept no trace")
def test_a_run_without_traces_is_dated_from_its_file_name(tmp_path: Path) -> None:
    """Checks a run with no trace starts at the time its name carries.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
    """
    # log.debug("Makes the results folder")
    results = tmp_path / "results"
    # log.debug("Creates it")
    results.mkdir()
    # log.debug("Writes a run with no traces, named as the evaluation names its files")
    (results / "live-20261029T144959Z.json").write_text(
        json.dumps({**RUN, "traces": []}), encoding="utf-8"
    )
    # log.debug("Reads the run")
    run = load_runs(results)[0]
    # log.debug("Checks it starts at the file name's time, in UTC")
    assert run["started_at"] == "2026-10-29T14:49:59+00:00"
    # log.debug("Checks the steps table is empty")
    assert len(frames([run])[2]) == 0


# log.debug("Defines the test of the figures command")
def test_command_writes_figures_beside_the_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Checks the figures go beside the runs when no path is given.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
        monkeypatch: pytest's helper for patching the environment and
            objects.
        capsys: pytest's capture of what the test prints.
    """
    # log.debug("Writes two runs")
    results = two_runs(tmp_path)
    # log.debug("Points [data] results at them")
    monkeypatch.setenv("DATA_RESULTS", str(results))
    # log.debug("Forgets any cached settings, so the command reads these")
    get_app_settings.cache_clear()
    # log.debug("Checks the command succeeds")
    assert main(["--export-figures"]) == 0
    # log.debug("Checks it says what it wrote")
    assert "(4 figures for t-2)" in capsys.readouterr().out
    # log.debug("Reads the file it wrote")
    written = json.loads((results / "figures.json").read_text(encoding="utf-8"))
    # log.debug("Checks it holds both runs")
    assert [r["run_id"] for r in written["runs"]] == ["t-2", "t-1"]


# log.debug("Defines the test that the app builds and serves its page")
@pytest.mark.filterwarnings(TABLE_DEPRECATED)
def test_app_builds(tmp_path: Path) -> None:
    """Checks the app lays out its page and serves it in its template.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
    """
    # log.debug("Builds the app over the run")
    app = build_app(one_run(tmp_path))
    # log.debug("Checks it has a layout")
    assert app.layout is not None
    # log.debug("Asks it for the page")
    page = app.server.test_client().get("/")
    # log.debug("Checks the page is served")
    assert page.status_code == 200
    # log.debug("Checks it is the site's template, with the app's title")
    assert "<title>New-matter intake agent: evaluation</title>" in page.text
