########################################################################
#               backend/src/intake_agent/api/schemas.py                #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           The HTTP request and response bodies, validated  #
#                     at the edge.                                     #
########################################################################
"""The HTTP request and response bodies.

Requests are validated here, at the edge: the email's
size, the decision's choices and the note's length. Responses reuse the
core models, so the API returns exactly what the core recorded.
"""

from __future__ import annotations

from typing import Literal

from kds.logs import get_logger
from pydantic import BaseModel, ConfigDict, Field

from intake_agent.config import NOTE_CEILING
from intake_agent.core.audit import RunRecord
from intake_agent.core.models import Decision, DraftRecord

# Module constants
log = get_logger(__name__)
# log.debug("Sets the hard ceiling on an email, above any setting")
CEILING_CHARS = 100_000
# log.debug("Sets the settings shared by every request body")
STRICT = ConfigDict(extra="forbid", frozen=True)
# log.debug("Lists the states the health check reports")
Status = Literal["ok"]


# log.debug("Defines an intake request")
class IntakeRequest(BaseModel):
    """The pasted intake email; settings set the exact length limits."""

    # log.debug("Refuses unknown fields and freezes the arguments")
    model_config = STRICT

    # log.debug("Holds the email")
    email: str = Field(min_length=1, max_length=CEILING_CHARS)


# log.debug("Defines an intake response")
class IntakeResponse(BaseModel):
    """The run's record, its draft if any, the agent's last words."""

    # log.debug("Holds the run")
    run: RunRecord
    # log.debug("Holds the draft")
    draft: DraftRecord | None
    # log.debug("Holds the agent's last words")
    text: str


# log.debug("Defines an approver's decision")
class DecisionRequest(BaseModel):
    """Approve or reject, with a note; a flag needs a reason."""

    # log.debug("Refuses unknown fields and freezes the arguments")
    model_config = STRICT

    # log.debug("Holds the decision")
    decision: Decision
    # log.debug("Holds the note")
    note: str = Field(default="", max_length=NOTE_CEILING)


# log.debug("Defines an example the web app offers")
class Example(BaseModel):
    """A made-up intake email from the evaluation, to try."""

    # log.debug("Holds the scenario id")
    id: str
    # log.debug("Holds its title")
    title: str
    # log.debug("Holds the email")
    email: str


# log.debug("Defines the health report")
class Health(BaseModel):
    """What is running, how sign-in works, and the database's size."""

    # log.debug("Holds the status")
    status: Status
    # log.debug("Holds the service version")
    version: str
    # log.debug("Holds the sign-in mode")
    auth_mode: str
    # log.debug("Holds the model provider")
    provider: str
    # log.debug("Holds the model")
    model: str
    # log.debug("Holds the client, matter and adverse party counts")
    firm: dict[str, int]
