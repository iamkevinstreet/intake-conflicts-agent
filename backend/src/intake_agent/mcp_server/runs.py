########################################################################
#                                                                      #
#             backend/src/intake_agent/mcp_server/runs.py              #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-07
Last modified on:  2026-11-07

Holds the intake runs an MCP client has open. Each run is the same as
one the agent makes: an audit record, and a toolbox scoped to the run
that checks every search, draft and approval request. The client acts
as the configured requester, with the requester role only.

A run ends when its draft is sent for approval, when the client ends
it, or when the server stops, and its audit record says which.
"""

########################################################################
#                                                                      #
#                               Imports                                #
#                                                                      #
########################################################################
# Standard library
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Final

# Third-party
from kds.args import missing, required
from kds.logs import get_logger, log_event

# Local
from intake_agent.api.state import Records
from intake_agent.config import SETTINGS, AppSettings
from intake_agent.core.guard import flag
from intake_agent.core.models import Actor, Outcome
from intake_agent.core.records import RunRecord, RunTotals
from intake_agent.core.service import check_email
from intake_agent.core.store import new_id
from intake_agent.core.tools import Toolbox

########################################################################
#                                                                      #
#                           Global constants                           #
#                                                                      #
########################################################################
log = get_logger(__name__)
# log.debug("Takes the milliseconds in a second, from the config")
MS: Final = SETTINGS.units_ms_per_second

########################################################################
#                                                                      #
#                           Local constants                            #
#                                                                      #
########################################################################
# log.debug("Sets the letter a run's id starts with, as the service's do")
RUN_PREFIX = "R"
# log.debug("Sets why a run still open when the server stops ends")
SERVER_STOPPED = "the MCP server stopped before the draft was sent for approval"


########################################################################
#                                                                      #
#                           MCP intake runs                            #
#                                                                      #
########################################################################
# log.debug("Defines one open run")
@dataclass
class OpenRun:
    """A run's toolbox, its calls so far, and when it started."""

    # log.debug("Holds the toolbox scoped to the run")
    toolbox: Toolbox
    # log.debug("Holds when the run started, for its time")
    started: float
    # log.debug("Holds how many tool calls the client has made")
    steps: int = 0


# log.debug("Defines the open runs of one MCP server")
class McpRuns:
    """Starts, finds and ends the runs an MCP client works on."""

    # log.debug("Defines the constructor")
    def __init__(
        self, records: Records | None = None, settings: AppSettings | None = None
    ) -> None:
        """Keeps the records the runs write to, and the settings.

        Args:
            records: The firm's records, the drafts and the audit log.
                Required.
            settings: The limits and the identity the client acts
                under. Required.
        """
        # log.debug("Takes the records, which the caller must give")
        self.records = required(records=records)
        # log.debug("Takes the settings, which the caller must give")
        self.settings = required(settings=settings)
        # log.debug("Starts with no open runs")
        self.open: dict[str, OpenRun] = {}

    # log.debug("Defines who an MCP client acts as")
    @property
    def requester(self) -> Actor:
        """Returns the configured requester, with that role alone.

        Returns:
            The identity every MCP run records, which the gate refuses
            whatever it asks.
        """
        # log.debug("Returns the identity, requester role only")
        return Actor(
            user_id=self.settings.mcp_requester_id,
            name=self.settings.mcp_requester_name,
            roles=frozenset({"requester"}),
        )

    # log.debug("Defines starting a run")
    def start(self, email: str | None = None) -> OpenRun:
        """Opens a run on the email, as the service would.

        Args:
            email: The pasted intake email. Required.

        Returns:
            The open run, whose toolbox carries the run's id.

        Raises:
            ValueError: The email is shorter or longer than allowed,
                or the client already has as many runs open as allowed.
        """
        # log.debug("Takes the email, which the caller must give")
        email = required(email=email)
        # log.debug("Checks the email's length, as the service does")
        check_email(email, self.settings)
        # log.debug("Refuses a run past the limit on open ones")
        if len(self.open) >= self.settings.mcp_max_open_runs:
            # log.debug("Explains how to make room")
            msg = (
                f"{len(self.open)} intakes are open already, the most allowed; send one for "
                "approval or end it first"
            )
            # log.debug("Raises the refusal")
            raise ValueError(msg)
        # log.debug("Names the run")
        run_id = new_id(RUN_PREFIX)
        # log.debug("Opens its audit record, for the configured requester")
        self.records.runlog.start(
            run_id, actor=self.requester, email=email, model=self.settings.mcp_model
        )
        # log.debug("Keeps the run with its own toolbox")
        self.open[run_id] = OpenRun(self._toolbox(run_id, email), time.perf_counter())
        # log.debug("Logs the run's start without the email's text")
        log_event(log, "mcp.run_started", run_id=run_id, open=len(self.open))
        # log.debug("Returns the run")
        return self.open[run_id]

    # log.debug("Defines finding an open run")
    def get(self, run_id: str | None = None) -> OpenRun:
        """Returns the open run with that id.

        Args:
            run_id: The id start returned. Required.

        Returns:
            The run.

        Raises:
            KeyError: No open run has that id.
        """
        # log.debug("Takes the id, which the caller must give")
        run_id = required(run_id=run_id)
        # log.debug("Returns the run, or raises for an id that is not open")
        return self.open[run_id]

    # log.debug("Defines ending a run")
    def finish(
        self,
        run_id: str | None = None,
        outcome: Outcome | None = None,
        reason: str | None = None,
    ) -> RunRecord:
        """Closes the run's audit record and forgets the run.

        Args:
            run_id: The open run's id. Required.
            outcome: How it ended. Required.
            reason: Why, in a sentence. Required.

        Returns:
            The finished audit record.
        """
        # log.debug("Takes the id, which the caller must give")
        run_id = required(run_id=run_id)
        # log.debug("Stops when the caller left out the outcome")
        if outcome is None:
            # log.debug("Raises the missing-argument error")
            raise missing(outcome=outcome)
        # log.debug("Takes the reason, which the caller must give")
        reason = required(reason=reason)
        # log.debug("Takes the run off the open list")
        run = self.open.pop(run_id)
        # log.debug("Closes its record: no tokens or cost, since the client's model is not ours")
        return self.records.runlog.finish(
            run_id,
            RunTotals(
                outcome=outcome,
                reason=reason,
                draft_id=run.toolbox.draft_id,
                steps=run.steps,
                tool_calls=run.toolbox.calls,
                input_tokens=0,
                output_tokens=0,
                cost_usd=None,
                ms=int((time.perf_counter() - run.started) * MS),
            ),
        )

    # log.debug("Defines ending every open run when the server stops")
    def close_all(self) -> int:
        """Ends every open run, saying the server stopped.

        Returns:
            How many runs were ended.
        """
        # log.debug("Lists the open runs first, since finishing changes the list")
        open_ids = list(self.open)
        # log.debug("Ends each as incomplete")
        for run_id in open_ids:
            # log.debug("Ends the run")
            self.finish(run_id, "incomplete", SERVER_STOPPED)
        # log.debug("Returns how many were ended")
        return len(open_ids)

    # log.debug("Defines the toolbox scoped to one run")
    def _toolbox(self, run_id: str | None = None, email: str | None = None) -> Toolbox:
        """Returns the toolbox the run's calls go through.

        Args:
            run_id: The run's id. Required.
            email: The intake email, whose order-giving lines the draft
                keeps for the approver. Required.

        Returns:
            The run's toolbox, as the service builds it.
        """
        # log.debug("Takes the id, which the caller must give")
        run_id = required(run_id=run_id)
        # log.debug("Takes the email, which the caller must give")
        email = required(email=email)
        # log.debug("Returns the toolbox, acting for the configured requester")
        return Toolbox(
            run_id=run_id,
            requester=self.requester,
            email=email,
            warnings=tuple(flag(email)),
            directory=self.records.directory,
            drafts=self.records.drafts,
            runlog=self.records.runlog,
            settings=self.settings,
        )
