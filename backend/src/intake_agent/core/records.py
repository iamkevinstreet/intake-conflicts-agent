########################################################################
#               backend/src/intake_agent/core/records.py               #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Defines the audit records as the audit log reads them back: a run, each
model call and tool call it made, and the totals a run finishes with.
Every record is frozen once built, as the database keeps it.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

from typing import Any

# Third-party
from kds.logs import get_logger
from pydantic import BaseModel, ConfigDict

# Local
from intake_agent.core.models import Outcome

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)

########################################################################
#                           Local constants                            #
########################################################################
# log.debug("Sets the settings shared by the audit records")
FROZEN = ConfigDict(frozen=True)


########################################################################
#                            Audit records                             #
########################################################################
# log.debug("Defines the record of one run")
class RunRecord(BaseModel):
    """A run: who, when, which email (hashed), outcome and cost."""

    # log.debug("Freezes the record once built")
    model_config = FROZEN

    # log.debug("Holds the run id")
    id: str
    # log.debug("Holds the requester's id")
    requester: str
    # log.debug("Holds the requester's name")
    requester_name: str
    # log.debug("Holds when it started, UTC")
    started_at: str
    # log.debug("Holds when it finished, UTC; empty while running")
    finished_at: str | None
    # log.debug("Holds the SHA-256 of the intake email")
    email_sha256: str
    # log.debug("Holds the email's length in characters")
    email_chars: int
    # log.debug("Holds the model the run used")
    model: str
    # log.debug("Holds how it ended")
    outcome: Outcome
    # log.debug("Holds why, in a sentence")
    reason: str
    # log.debug("Holds the draft it made, if any")
    draft_id: str | None
    # log.debug("Holds how many model calls it made")
    steps: int
    # log.debug("Holds how many tool calls it made")
    tool_calls: int
    # log.debug("Holds the tokens the model read")
    input_tokens: int
    # log.debug("Holds the tokens the model wrote")
    output_tokens: int
    # log.debug("Holds the cost in US dollars; empty for an unpriced model")
    cost_usd: float | None
    # log.debug("Holds the run's wall-clock time in milliseconds")
    ms: int


# log.debug("Defines the record of one model call")
class ModelCallRecord(BaseModel):
    """One call to the model: tokens, cost, time, why it stopped."""

    # log.debug("Freezes the record once built")
    model_config = FROZEN

    # log.debug("Holds the step number, from 1")
    step: int
    # log.debug("Holds the tokens read")
    input_tokens: int
    # log.debug("Holds the tokens written")
    output_tokens: int
    # log.debug("Holds the cost")
    cost_usd: float | None
    # log.debug("Holds the time taken")
    ms: int
    # log.debug("Holds why the model stopped")
    stop_reason: str


# log.debug("Defines the record of one tool call")
class ToolCallRecord(BaseModel):
    """One tool call: what was asked, if it worked, what came back."""

    # log.debug("Freezes the record once built")
    model_config = FROZEN

    # log.debug("Holds the call's place in the run, from 1")
    seq: int
    # log.debug("Holds the model call that asked for it")
    step: int
    # log.debug("Holds the tool's name")
    tool: str
    # log.debug("Holds the arguments, redacted")
    arguments: dict[str, Any]
    # log.debug("Holds whether it worked")
    ok: bool
    # log.debug("Holds the refusal or error, if it did not")
    error: str
    # log.debug("Holds the SHA-256 of what came back")
    result_sha256: str
    # log.debug("Holds the time taken")
    ms: int
    # log.debug("Holds when, UTC")
    at: str


# log.debug("Defines a run with all its calls")
class RunDetail(BaseModel):
    """A run and every call it made, in order."""

    # log.debug("Freezes the record once built")
    model_config = FROZEN

    # log.debug("Holds the run")
    run: RunRecord
    # log.debug("Holds its model calls")
    model_calls: list[ModelCallRecord]
    # log.debug("Holds its tool calls")
    tool_calls: list[ToolCallRecord]


# log.debug("Defines the totals a run finishes with")
class RunTotals(BaseModel):
    """How a run ended and what it used."""

    # log.debug("Freezes the record once built")
    model_config = FROZEN

    # log.debug("Holds how it ended")
    outcome: Outcome
    # log.debug("Holds why")
    reason: str
    # log.debug("Holds the draft it made")
    draft_id: str | None
    # log.debug("Holds the model calls")
    steps: int
    # log.debug("Holds the tool calls")
    tool_calls: int
    # log.debug("Holds the tokens read")
    input_tokens: int
    # log.debug("Holds the tokens written")
    output_tokens: int
    # log.debug("Holds the cost")
    cost_usd: float | None
    # log.debug("Holds the time")
    ms: int
