########################################################################
#                backend/src/intake_agent/evals/run.py                 #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           Runs the scenarios on a fresh database, checks   #
#                     the gate, writes the results.                    #
########################################################################
"""Runs the twenty scenarios and writes the results.

    python -m intake_agent.evals.run --name offline
    python -m intake_agent.evals.run --name live --only s04 s18

Each evaluation builds a fresh firm database in a temporary folder
from the same seed, so runs never see each other's drafts. After each
run, an approver identity tries to open the run's draft without an
approval; the gate must refuse every time. Results go to
data/evals/results as JSON (every score, and each run's calls and
draft) and Markdown (the table), with a -latest.md copy the README
links to.
"""

from __future__ import annotations

import argparse
import tempfile
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kds.llm.pricing import prices_as_of
from kds.logs import get_logger, log_event, setup_logging
from pydantic import BaseModel

from intake_agent.config import AppSettings, get_app_settings
from intake_agent.core.audit import RunDetail, RunLog
from intake_agent.core.drafts import DraftBook, GateError
from intake_agent.core.firm import SqliteDirectory
from intake_agent.core.models import Actor
from intake_agent.core.offline import adapter_for
from intake_agent.core.seed import seed
from intake_agent.core.service import IntakeResult, IntakeService
from intake_agent.core.store import Store
from intake_agent.evals.scenarios import Scenario, directory_for, load_scenarios
from intake_agent.evals.score import ScenarioScore, score, summarise

# Module constants
log = get_logger(__name__)
# log.debug("Sets the requester every scenario runs as")
REQUESTER = Actor(user_id="eval:requester", name="Evaluation", roles=frozenset({"requester"}))
# log.debug("Sets the approver that tries to open each draft without approval")
GATE_CHECKER = Actor(user_id="eval:approver", name="Gate check", roles=frozenset({"approver"}))
# log.debug("Sets the file encoding")
ENCODING = "utf-8"
# log.debug("Leaves the email out of saved drafts: the scenarios file holds it")
UNSAVED = frozenset({"email"})
# log.debug("Lists the measures in the order the table shows them, with labels")
ROWS = (
    ("conflict_recall", "Conflict recall: planted records in the findings"),
    ("false_positive_rate", "False positives: clean scenarios shown as conflicts"),
    ("clean_flagged_for_review", "Clean scenarios sent to review"),
    ("escalation", "Escalation: ambiguous scenarios the agent marked review"),
    ("verdict_accuracy", "Verdict shown to the approver matches the expected one"),
    ("agent_verdict_accuracy", "Agent's own verdict matches the expected one"),
    ("failure_handling", "Failure handling: timeout, non-intakes, injections"),
    ("parties_named", "Parties the draft named, of those in the emails"),
    ("opened_without_approval", "Matters opened without an approval record"),
    ("open_attempts", "Times the agent called open_matter"),
    ("median_seconds", "Median seconds per scenario"),
    ("p95_seconds", "95th-percentile seconds per scenario"),
    ("mean_cost_usd", "Mean cost per scenario, USD"),
    ("total_cost_usd", "Total cost, USD"),
)


# log.debug("Defines what the agent did on one scenario")
class ScenarioTrace(BaseModel):
    """One scenario's run: its calls, its draft and the agent's text."""

    # log.debug("Holds the scenario id")
    id: str
    # log.debug("Holds the run with its model and tool calls")
    detail: RunDetail | None
    # log.debug("Holds the draft as the approver saw it, without the email")
    draft: dict[str, Any] | None
    # log.debug("Holds the agent's last words")
    text: str


# log.debug("Defines what one evaluation produced")
class EvalResults(BaseModel):
    """The run's name, the model, the measures and every score."""

    # log.debug("Holds the results' name, such as offline")
    name: str
    # log.debug("Holds the model the runs used")
    model: str
    # log.debug("Holds the provider")
    provider: str
    # log.debug("Holds the date of the price table costs came from")
    prices_as_of: str
    # log.debug("Holds the measures")
    summary: dict[str, Any]
    # log.debug("Holds every scenario's score")
    scenarios: list[ScenarioScore]
    # log.debug("Holds what the agent did on each scenario")
    traces: list[ScenarioTrace]


# log.debug("Defines one evaluation")
def run_eval(
    settings: AppSettings,
    *,
    name: str,
    only: Sequence[str] = (),
    sleep: Callable[[float], None] = time.sleep,
) -> EvalResults:
    """Run the scenarios (all, or `only`); return the results."""
    # log.debug("Loads the scenarios, keeping the ones asked for")
    scenarios = [s for s in load_scenarios(settings.data_scenarios) if not only or s.id in only]
    # log.debug("Builds the model adapter the settings name")
    adapter = adapter_for(settings)
    # log.debug("Works in a temporary folder the run deletes")
    with tempfile.TemporaryDirectory() as folder:
        # log.debug("Builds and seeds a fresh firm database")
        store = Store(Path(folder) / "firm.sqlite", timeout_s=settings.store_timeout_s)
        # log.debug("Seeds it")
        seed(store, settings)
        # log.debug("Builds the drafts book")
        drafts = DraftBook(store, min_reason_chars=settings.api_min_reason_chars)
        # log.debug("Builds the service")
        service = IntakeService(
            settings=settings,
            directory=SqliteDirectory(store),
            drafts=drafts,
            runlog=RunLog(store),
            adapter=adapter,
            sleep=sleep,
        )
        # log.debug("Runs, traces and scores each scenario")
        done = [_one(service, drafts, scenario) for scenario in scenarios]
    # log.debug("Separates the scores")
    scores = [scored for scored, _ in done]
    # log.debug("Returns everything the results files hold")
    return EvalResults(
        name=name,
        model=adapter.model,
        provider=settings.llm_provider,
        prices_as_of=prices_as_of(),
        summary=summarise(scores),
        scenarios=scores,
        traces=[trace for _, trace in done],
    )


# log.debug("Defines one scenario's run, trace, gate check and score")
def _one(
    service: IntakeService, drafts: DraftBook, scenario: Scenario
) -> tuple[ScenarioScore, ScenarioTrace]:
    """Run it, keep its trace, try to open its draft, and score it."""
    # log.debug("Starts the clock")
    started = time.perf_counter()
    # log.debug("Runs the intake, with the scenario's fault if it has one")
    result = service.run(scenario.email, REQUESTER, directory=directory_for(scenario))
    # log.debug("Stops the clock")
    seconds = time.perf_counter() - started
    # log.debug("Logs the scenario's ending")
    log_event(log, "eval.scenario", id=scenario.id, outcome=result.run.outcome)
    # log.debug("Keeps what the agent did, read back from the audit records")
    trace = ScenarioTrace(
        id=scenario.id,
        detail=service.runlog.detail(result.run.id),
        draft=result.draft.draft.model_dump(mode="json", exclude=set(UNSAVED))
        if result.draft
        else None,
        text=result.text,
    )
    # log.debug("Checks the gate, then scores the run")
    opened = _opens_unapproved(drafts, result)
    # log.debug("Returns the score and the trace")
    return score(scenario, result, seconds=seconds, opened=opened), trace


# log.debug("Defines the gate check: may an approver open this draft before approval?")
def _opens_unapproved(drafts: DraftBook, result: IntakeResult) -> bool:
    """Return True if the draft could be opened without an approval."""
    # log.debug("Nothing to open without a draft")
    if result.draft is None:
        # log.debug("Returns not opened")
        return False
    # log.debug("Tries to open it as an approver, with no approval record")
    try:
        # log.debug("Asks the gate")
        drafts.open(result.draft.draft.id, actor=GATE_CHECKER)
    except GateError:
        # log.debug("Returns not opened: the gate held")
        return False
    # log.debug("Returns opened: the gate failed")
    return True


# log.debug("Defines the Markdown report")
def to_markdown(results: EvalResults) -> str:
    """Return the measures table and one line per scenario."""
    # log.debug("Writes the heading and the measures")
    lines = [
        f"# Evaluation: {results.name}",
        "",
        f"Model `{results.model}` ({results.provider}), {len(results.scenarios)} scenarios, "
        f"prices as of {results.prices_as_of}.",
        "",
        "| Measure | Value |",
        "| --- | --- |",
        *(f"| {label} | {_cell(results.summary[key])} |" for key, label in ROWS),
        "",
        "| Scenario | Outcome | Shown | Agent | Checks | Expected | Found | Handled |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    # log.debug("Adds one row per scenario")
    lines += [
        f"| {s.id} {s.title} | {s.outcome} | {_cell(s.recommendation)} | "
        f"{_cell(s.agent_recommendation)} | {_cell(s.checks_recommendation)} | "
        f"{_cell(s.expected_recommendation)} | {s.found}/{s.planted} | {_cell(s.handled)} |"
        for s in results.scenarios
    ]
    # log.debug("Returns the report")
    return "\n".join(lines) + "\n"


# log.debug("Defines how a value is written in a table cell")
def _cell(value: Any) -> str:
    """Return a dash for None, yes or no for booleans, or text."""
    # log.debug("Writes None as a dash")
    if value is None:
        # log.debug("Returns the dash")
        return "-"
    # log.debug("Writes booleans as yes or no")
    if isinstance(value, bool):
        # log.debug("Returns yes or no")
        return "yes" if value else "no"
    # log.debug("Returns anything else as text")
    return str(value)


# log.debug("Defines where the results are written")
def write(results: EvalResults, folder: Path) -> Path:
    """Write JSON, Markdown and the -latest copy; return JSON."""
    # log.debug("Creates the folder")
    folder.mkdir(parents=True, exist_ok=True)
    # log.debug("Stamps the files with the time, UTC")
    stem = f"{results.name}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    # log.debug("Writes the JSON")
    (folder / f"{stem}.json").write_text(results.model_dump_json(indent=2) + "\n", ENCODING)
    # log.debug("Renders the Markdown once")
    report = to_markdown(results)
    # log.debug("Writes the dated Markdown")
    (folder / f"{stem}.md").write_text(report, encoding=ENCODING)
    # log.debug("Writes the copy the README links to")
    (folder / f"{results.name}-latest.md").write_text(report, encoding=ENCODING)
    # log.debug("Returns the JSON's path")
    return folder / f"{stem}.json"


# log.debug("Defines the command line")
def main(argv: Sequence[str] | None = None) -> int:
    """Run the evaluation from the command line; return status."""
    # log.debug("Describes the arguments")
    parser = argparse.ArgumentParser(description="Run the intake evaluation.")
    # log.debug("Adds the results name")
    parser.add_argument("--name", required=True, help="results file prefix, such as offline")
    # log.debug("Adds the optional scenario filter")
    parser.add_argument("--only", nargs="*", default=[], help="scenario ids to run")
    # log.debug("Reads the arguments")
    args = parser.parse_args(argv)
    # log.debug("Reads the settings")
    settings = get_app_settings()
    # log.debug("Sets up logging")
    setup_logging(settings)
    # log.debug("Runs the evaluation")
    results = run_eval(settings, name=args.name, only=args.only)
    # log.debug("Writes the results")
    path = write(results, settings.data_results)
    # log.debug("Prints the table")
    print(to_markdown(results))
    # log.debug("Logs where the results went")
    log_event(log, "eval.done", path=str(path), **results.summary)
    # log.debug("Fails the command if the gate ever let a matter open")
    return 1 if results.summary["opened_without_approval"] else 0


# log.debug("Runs main when the module is run as a script")
if __name__ == "__main__":
    # log.debug("Exits with main's status")
    raise SystemExit(main())
