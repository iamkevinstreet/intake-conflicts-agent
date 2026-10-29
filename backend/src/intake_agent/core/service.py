########################################################################
#               backend/src/intake_agent/core/service.py               #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Runs one intake end to end, the path the API and the evaluation share.
It opens the run's audit record, flags order-giving lines in the email,
gives the agent a toolbox scoped to this run, runs the loop, and closes
the record with how the run ended and what it cost, even when the model
fails part way. The email is checked here as well as at the API, so the
evaluation meets the same limits.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

# Third-party
from kds.args import required
from kds.llm import BudgetExceededError, ModelAdapter
from kds.llm.errors import is_transient
from kds.logs import get_logger, log_event

# Local
from intake_agent.config import SETTINGS, AppSettings
from intake_agent.core.agent import Ending, IntakeAgent, Meter
from intake_agent.core.audit import RunLog
from intake_agent.core.drafts import DraftBook
from intake_agent.core.firm import Directory
from intake_agent.core.guard import flag
from intake_agent.core.models import Actor, DraftRecord
from intake_agent.core.records import RunRecord, RunTotals
from intake_agent.core.store import new_id
from intake_agent.core.tools import Toolbox

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)
# log.debug("Takes the milliseconds in a second, from the config")
MS: Final = SETTINGS.units_ms_per_second


########################################################################
#                            Intake service                            #
########################################################################
# log.debug("Defines the result of one intake")
@dataclass(frozen=True)
class IntakeResult:
    """The finished run, its draft if any, the model's last words."""

    # log.debug("Holds the run's audit record")
    run: RunRecord
    # log.debug("Holds the draft, if one was saved")
    draft: DraftRecord | None
    # log.debug("Holds the model's last words")
    text: str
    # log.debug("Holds how many times the agent tried to open a matter")
    open_attempts: int


# log.debug("Defines the intake service")
@dataclass(frozen=True)
class IntakeService:
    """Runs intakes; every collaborator is passed in."""

    # log.debug("Holds the settings")
    settings: AppSettings
    # log.debug("Holds the read-only view of the firm")
    directory: Directory
    # log.debug("Holds the drafts")
    drafts: DraftBook
    # log.debug("Holds the audit log")
    runlog: RunLog
    # log.debug("Holds the model adapter")
    adapter: ModelAdapter
    # log.debug("Holds how to wait between search retries")
    sleep: Callable[[float], None] = time.sleep

    # log.debug("Defines one intake")
    def run(
        self,
        email: str | None = None,
        requester: Actor | None = None,
        *,
        directory: Directory | None = None,
    ) -> IntakeResult:
        """Runs one intake for `requester` and returns how it ended.

        Args:
            email: The pasted intake email. Required.
            requester: Who asked; the agent acts for them, as a
                requester only. Required.
            directory: A stand-in for the firm's records; the evaluation
                passes one that times out.

        Returns:
            The finished run's audit record, its draft if one was
            saved, the model's last words and how often the agent
            tried to open a matter.

        Raises:
            ValueError: The email is shorter or longer than allowed.
        """
        # log.debug("Takes the email, which the caller must give")
        email = required(email=email)
        # log.debug("Takes the requester, which the caller must give")
        requester = required(requester=requester)
        # log.debug("Checks the email's length before anything is recorded")
        self._check(email)
        # log.debug("Names the run")
        run_id = new_id("R")
        # log.debug("Opens the run's audit record")
        self.runlog.start(run_id, actor=requester, email=email, model=self.adapter.model)
        # log.debug("Builds the toolbox for this run alone")
        toolbox = Toolbox(
            run_id=run_id,
            requester=requester,
            email=email,
            warnings=tuple(flag(email)),
            directory=directory or self.directory,
            drafts=self.drafts,
            runlog=self.runlog,
            settings=self.settings,
            sleep=self.sleep,
        )
        # log.debug("Starts the meter and the clock")
        meter, started = Meter(), time.perf_counter()
        # log.debug("Runs the agent, ending the run as failed on any model error")
        ending = self._attempt(email, toolbox, meter)
        # log.debug("Closes the audit record with the outcome and the totals")
        record = self.runlog.finish(
            run_id,
            RunTotals(
                outcome=ending.outcome,
                reason=ending.reason,
                draft_id=toolbox.draft_id,
                steps=meter.steps,
                tool_calls=toolbox.calls,
                input_tokens=meter.input_tokens,
                output_tokens=meter.output_tokens,
                cost_usd=meter.cost,
                ms=int((time.perf_counter() - started) * MS),
            ),
        )
        # log.debug("Reads the draft back, if one was saved")
        draft = self.drafts.get(toolbox.draft_id) if toolbox.draft_id else None
        # log.debug("Returns the result")
        return IntakeResult(record, draft, ending.text, toolbox.open_attempts)

    # log.debug("Defines the length check")
    def _check(self, email: str | None = None) -> None:
        """Refuses an email outside the configured length.

        Args:
            email: The pasted intake email. Required.

        Raises:
            ValueError: Too short or too long; the message gives the
                limits.
        """
        # log.debug("Takes the email, which the caller must give")
        email = required(email=email)
        # log.debug("Measures the email without surrounding space")
        length = len(email.strip())
        # log.debug("Refuses one outside the limits")
        if (
            not self.settings.agent_min_email_chars
            <= length
            <= self.settings.agent_max_email_chars
        ):
            # log.debug("Explains the limits")
            msg = (
                f"an intake email must be {self.settings.agent_min_email_chars} to "
                f"{self.settings.agent_max_email_chars} characters; this one is {length}"
            )
            # log.debug("Raises the refusal")
            raise ValueError(msg)

    # log.debug("Defines the guarded run of the agent")
    def _attempt(
        self, email: str | None = None, toolbox: Toolbox | None = None, meter: Meter | None = None
    ) -> Ending:
        """Runs the agent; any model failure becomes a failed ending.

        Args:
            email: The pasted intake email. Required.
            toolbox: The tools scoped to this run. Required.
            meter: Counts what the run spends, which the caller reads
                even when the run fails. Required.

        Returns:
            How the run ended: the agent's own ending, or failed with
            the reason a model call failed.
        """
        # log.debug("Takes the email, which the caller must give")
        email = required(email=email)
        # log.debug("Takes the toolbox, which the caller must give")
        toolbox = required(toolbox=toolbox)
        # log.debug("Takes the meter, which the caller must give")
        meter = required(meter=meter)
        # log.debug("Runs the agent")
        try:
            # log.debug("Returns how it ended")
            return IntakeAgent(self.adapter, self.settings).run(email, toolbox, meter)
        except BudgetExceededError:
            # log.debug("Explains a spent process budget")
            reason = "the model budget for this service is spent"
        except Exception as error:  # noqa: BLE001 - any error must still close the run
            # log.debug("Explains the failure: an outage, or an error nobody planned for")
            reason = _failure(error)
        # log.debug("Returns the failed ending")
        return Ending("failed", reason)


# log.debug("Defines how a failed model call is explained")
def _failure(error: Exception | None = None) -> str:
    """Returns why a run failed, logging the errors nobody planned for.

    A provider outage that outlasted the adapter's retries arrives as
    the SDK's own error, so it is recognised by kind, not by class.

    Args:
        error: The error the agent's run raised. Required.

    Returns:
        The reason the run's record gives: an outage, or the error's
        type.
    """
    # log.debug("Takes the error, which the caller must give")
    error = required(error=error)
    # log.debug("Explains a model that could not be reached, after the retries")
    if is_transient(error):
        # log.debug("Returns the outage reason")
        return "the model could not be reached; try again later"
    # log.debug("Logs the error's type, never its message, which may hold data")
    log_event(log, "run.error", logging.ERROR, error=type(error).__name__)
    # log.debug("Explains the failure by its type")
    return f"the run failed ({type(error).__name__})"
