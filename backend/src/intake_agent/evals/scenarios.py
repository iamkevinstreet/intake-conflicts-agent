########################################################################
#             backend/src/intake_agent/evals/scenarios.py              #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Loads the twenty scenarios and supplies the database timeout one of them
needs. data/evals/scenarios.jsonl holds twenty intake emails, each with
what should happen: the parties, the planted records the checks should
find, the verdict and how the run should end. data/README.md describes
the file; a test proves every expectation holds against the generated
database before any model is asked.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

# Third-party
from kds.args import required
from kds.logs import get_logger
from pydantic import BaseModel, Field

# Local
from intake_agent.core.firm import AdverseRecord, ClientRecord, Directory
from intake_agent.core.models import Outcome, Recommendation, RecordKind
from intake_agent.core.store import StoreTimeoutError

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)

########################################################################
#                           Local constants                            #
########################################################################
# log.debug("Lists the groups the measures are reported by")
Category = Literal["conflict", "ambiguous", "clean", "failure"]
# log.debug("Lists the faults a scenario can inject")
Fault = Literal["db_timeout"]
# log.debug("Sets the message of the simulated timeout")
TIMEOUT = "simulated: the database did not answer"


########################################################################
#                         Evaluation scenarios                         #
########################################################################
# log.debug("Defines a record the checks should find")
class Planted(BaseModel):
    """A planted record in data/samples/firm.json."""

    # log.debug("Holds which table it is in")
    kind: RecordKind
    # log.debug("Holds its exact name there")
    name: str


# log.debug("Defines what should happen")
class Expected(BaseModel):
    """The parties, the planted findings, the verdict and the ending."""

    # log.debug("Holds the prospective client, or None for a non-intake")
    client: str | None
    # log.debug("Holds the parties on the other side")
    adverse: list[str]
    # log.debug("Holds the records the checks should find")
    planted: list[Planted]
    # log.debug("Holds the verdict, or None when no draft should be made")
    recommendation: Recommendation | None
    # log.debug("Holds how the run should end")
    outcome: Outcome


# log.debug("Defines one scenario")
class Scenario(BaseModel):
    """An intake email and what should happen to it."""

    # log.debug("Holds the id, s01 to s20")
    id: str = Field(pattern=r"^s\d{2}$")
    # log.debug("Holds a short title")
    title: str
    # log.debug("Holds its group")
    category: Category
    # log.debug("Holds tags such as near_duplicate or injection")
    tags: list[str]
    # log.debug("Holds the fault to inject, if any")
    fault: Fault | None
    # log.debug("Holds the email")
    email: str
    # log.debug("Holds what should happen")
    expected: Expected


# log.debug("Defines the loader")
def load_scenarios(path: Path | None = None) -> list[Scenario]:
    """Returns the scenarios in file order.

    Args:
        path: The scenarios file, one JSON object per line. Required.

    Returns:
        Every scenario, validated, in file order.

    Raises:
        ValueError: Two scenarios share an id.
    """
    # log.debug("Takes the path, which the caller must give")
    path = required(path=path)
    # log.debug("Parses each non-empty line")
    scenarios = [
        Scenario.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    # log.debug("Refuses repeated ids")
    if len({s.id for s in scenarios}) != len(scenarios):
        # log.debug("Words the refusal")
        msg = f"{path} repeats a scenario id"
        # log.debug("Raises the refusal")
        raise ValueError(msg)
    # log.debug("Returns them")
    return scenarios


# log.debug("Defines a firm database that never answers")
class TimeoutDirectory:
    """Every read times out, like a locked or unreachable database."""

    # log.debug("Defines the client read, which times out")
    def clients(self) -> list[ClientRecord]:
        """Raises a timeout.

        Returns:
            Nothing: the read always times out.

        Raises:
            StoreTimeoutError: Always.
        """
        # log.debug("Raises the timeout")
        raise StoreTimeoutError(TIMEOUT)

    # log.debug("Defines the adverse-party read, which times out")
    def adverse_parties(self) -> list[AdverseRecord]:
        """Raises a timeout.

        Returns:
            Nothing: the read always times out.

        Raises:
            StoreTimeoutError: Always.
        """
        # log.debug("Raises the timeout")
        raise StoreTimeoutError(TIMEOUT)


# log.debug("Defines the directory a scenario runs against")
def directory_for(scenario: Scenario | None = None) -> Directory | None:
    """Returns a failing directory for a timeout scenario, else None.

    Args:
        scenario: The scenario about to run. Required.

    Returns:
        A directory whose every read times out when the scenario
        injects that fault, else None, which keeps the real one.
    """
    # log.debug("Takes the scenario, which the caller must give")
    scenario = required(scenario=scenario)
    # log.debug("Returns the failing one only when the scenario asks")
    return TimeoutDirectory() if scenario.fault == "db_timeout" else None
