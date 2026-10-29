########################################################################
#                backend/src/intake_agent/core/tools.py                #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Holds the five tools for one run: read-only searches, one checked draft,
and a gated open.

- Both searches only read, through `Directory`, and retry a timed-out
  read a bounded number of times before reporting failure
  (core/searches.py).
- draft_matter writes one draft per run, only after every party on it
  was searched, and computes the findings itself from those searches:
  the agent cannot leave a match out or change its severity.
- request_approval sends only this run's own draft.
- open_matter goes through the same gate as the approver's button, with
  the requester's role only, so it is always refused.

Every call is validated, timed and written to the audit log, and none
raises: refusals and failures go back to the model as JSON, so it can
read why and stop or correct itself.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Final

# Third-party
from kds.args import required
from kds.logs import get_logger
from pydantic import ValidationError

# Local
from intake_agent.config import SETTINGS, AppSettings
from intake_agent.core import prompt
from intake_agent.core.audit import RunLog
from intake_agent.core.conflicts import stricter, verdict
from intake_agent.core.drafts import DraftBook, DraftError
from intake_agent.core.firm import Directory
from intake_agent.core.models import (
    Actor,
    Draft,
    DraftArgs,
    Finding,
    OpenArgs,
    SubmitArgs,
    ToolReply,
)
from intake_agent.core.names import normalize
from intake_agent.core.searches import SearchResult, SearchTools
from intake_agent.core.store import new_id, utc_now

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)
# log.debug("Takes the milliseconds in a second, from the config")
MS: Final = SETTINGS.units_ms_per_second

########################################################################
#                           Local constants                            #
########################################################################
# log.debug("Names the error key every refusal carries")
ERROR = prompt.ERROR_KEY
# log.debug("Names the key that tells the model what to do next")
NEXT = prompt.NEXT_KEY
# log.debug("Names the key that carries a draft id")
DRAFT_ID_KEY = prompt.DRAFT_ID_KEY
# log.debug("Names the audit code for a refused call")
REFUSED = "refused"


########################################################################
#                             Run toolbox                              #
########################################################################
# log.debug("Defines the toolbox one run uses")
@dataclass
class Toolbox(SearchTools):
    """The five tools for one run, and what the run did with them."""

    # log.debug("Holds the run's id")
    run_id: str
    # log.debug("Holds the requester the agent acts for")
    requester: Actor
    # log.debug("Holds the intake email, which the draft keeps for the approver")
    email: str
    # log.debug("Holds the email's order-giving lines, for the draft")
    warnings: tuple[str, ...]
    # log.debug("Holds the read-only view of the firm")
    directory: Directory
    # log.debug("Holds the drafts")
    drafts: DraftBook
    # log.debug("Holds the audit log")
    runlog: RunLog
    # log.debug("Holds the settings")
    settings: AppSettings
    # log.debug("Holds how to wait between retries; tests pass a no-op")
    sleep: Callable[[float], None] = time.sleep
    # log.debug("Holds every search so far, by tool and plain name")
    searched: dict[tuple[str, str], SearchResult] = field(default_factory=dict)
    # log.debug("Holds the run's draft id, once saved")
    draft_id: str | None = None
    # log.debug("Holds whether the draft was sent for approval")
    submitted: bool = False
    # log.debug("Holds how many times the agent tried to open a matter")
    open_attempts: int = 0
    # log.debug("Holds how many calls have been made")
    calls: int = 0

    # log.debug("Defines the agent's identity: the requester, with no approver role")
    @property
    def agent(self) -> Actor:
        """Returns the requester's identity, requester role only.

        Returns:
            The requester's id and name with the requester role alone,
            so the gate refuses the agent even when its user is also
            an approver.
        """
        # log.debug("Returns it, so a user with both roles still cannot open")
        return Actor(
            user_id=self.requester.user_id,
            name=self.requester.name,
            roles=frozenset({"requester"}),
        )

    # log.debug("Defines one tool call: validate, run, audit, reply")
    def call(
        self,
        name: str | None = None,
        arguments: dict[str, Any] | None = None,
        *,
        step: int | None = None,
    ) -> ToolReply:
        """Runs one tool call and records it; never raises.

        Args:
            name: The tool the model asked for. Required.
            arguments: The arguments the model gave, not yet
                validated. Required.
            step: The model call that asked for it, from 1. Required.

        Returns:
            What the tool did, which the model reads, with the audit
            code when it did not work.
        """
        # log.debug("Takes the tool's name, which the caller must give")
        name = required(name=name)
        # log.debug("Takes the arguments, which the caller must give")
        arguments = required(arguments=arguments)
        # log.debug("Takes the step, which the caller must give")
        step = required(step=step)
        # log.debug("Numbers the call")
        self.calls += 1
        # log.debug("Starts the clock")
        started = time.perf_counter()
        # log.debug("Runs the tool, turning refusals into replies")
        reply = self._dispatch(name, arguments)
        # log.debug("Writes the call to the audit log")
        self.runlog.tool_call(
            self.run_id,
            seq=self.calls,
            step=step,
            tool=name,
            arguments=arguments,
            ok=reply.ok,
            error=reply.code,
            result=reply.payload,
            ms=int((time.perf_counter() - started) * MS),
        )
        # log.debug("Returns the reply")
        return reply

    # log.debug("Defines the dispatch to the named tool")
    def _dispatch(
        self, name: str | None = None, arguments: dict[str, Any] | None = None
    ) -> ToolReply:
        """Returns the tool's reply, or why it was refused.

        Args:
            name: The tool the model asked for. Required.
            arguments: The arguments the model gave, not yet
                validated. Required.

        Returns:
            The tool's reply, or a refusal for an unknown tool, for
            invalid arguments, or for an action the draft book
            refused.
        """
        # log.debug("Takes the tool's name, which the caller must give")
        name = required(name=name)
        # log.debug("Takes the arguments, which the caller must give")
        arguments = required(arguments=arguments)
        # log.debug("Maps each tool name to its handler")
        handlers: dict[str, Callable[[dict[str, Any]], ToolReply]] = {
            prompt.SEARCH_CLIENTS: self._search_clients,
            prompt.SEARCH_ADVERSE: self._search_adverse,
            prompt.DRAFT_MATTER: self._draft,
            prompt.REQUEST_APPROVAL: self._submit,
            prompt.OPEN_MATTER: self._open,
        }
        # log.debug("Refuses a tool that does not exist")
        if name not in handlers:
            # log.debug("Returns the refusal")
            return ToolReply(False, {ERROR: f"there is no tool named {name}"}, "unknown_tool")
        # log.debug("Runs the handler")
        try:
            # log.debug("Returns its reply")
            return handlers[name](arguments)
        except ValidationError as error:
            # log.debug("Explains which arguments were wrong")
            details = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors()]
            # log.debug("Returns the refusal")
            return ToolReply(False, {ERROR: "invalid arguments", "details": details}, "invalid")
        except DraftError as error:
            # log.debug("Returns the draft book's refusal")
            return ToolReply(False, {ERROR: str(error)}, REFUSED)

    # log.debug("Defines draft_matter")
    def _draft(self, arguments: dict[str, Any] | None = None) -> ToolReply:
        """Saves the run's one draft, with findings from its searches.

        Args:
            arguments: The model's arguments for draft_matter, not yet
                validated. Required.

        Returns:
            The saved draft's id, how many findings it holds and the
            checks' verdict, or why it was refused.
        """
        # log.debug("Takes the arguments, which the caller must give")
        arguments = required(arguments=arguments)
        # log.debug("Validates the arguments")
        args = DraftArgs.model_validate(arguments)
        # log.debug("Refuses a second draft")
        if self.draft_id is not None:
            # log.debug("Points to the draft already saved")
            return self._refuse(f"this run already saved {self.draft_id}; call request_approval")
        # log.debug("Removes repeated parties, keeping the first spelling")
        adverse = unique(args.adverse_parties)
        # log.debug("Refuses more parties than settings allow")
        if len(adverse) > self.settings.agent_max_parties:
            # log.debug("Returns the refusal")
            return self._refuse(f"at most {self.settings.agent_max_parties} adverse parties")
        # log.debug("Lists each search the draft needs: the client, then each adverse party")
        needed = [(prompt.SEARCH_ADVERSE, args.client)] + [
            (prompt.SEARCH_CLIENTS, party) for party in adverse
        ]
        # log.debug("Finds searches that failed")
        failed = [f"{tool}: {name}" for tool, name in needed if not self._result(tool, name).ok]
        # log.debug("Finds searches never made")
        missing = [f"{tool}: {name}" for tool, name in needed if self._unsearched(tool, name)]
        # log.debug("Refuses a draft whose checks are not complete")
        if missing or failed:
            # log.debug("Says what to do")
            return ToolReply(
                False,
                {ERROR: "search every party first", "missing": missing, "failed": failed},
                "unsearched",
            )
        # log.debug("Computes the findings from the run's own searches")
        found = self._findings(args.client, adverse)
        # log.debug("Builds the draft")
        draft = self._build(args, adverse, found)
        # log.debug("Saves it")
        self.drafts.save(draft)
        # log.debug("Remembers its id")
        self.draft_id = draft.id
        # log.debug("Tells the model what was saved and what comes next")
        return ToolReply(
            True,
            {
                DRAFT_ID_KEY: draft.id,
                "findings": len(found),
                "checks_recommendation": draft.checks_recommendation,
                NEXT: "call request_approval with this draft_id",
            },
        )

    # log.debug("Defines the draft built from the agent's reading and the checks")
    def _build(
        self,
        args: DraftArgs | None = None,
        adverse: list[str] | None = None,
        found: list[Finding] | None = None,
    ) -> Draft:
        """Returns the draft: the agent's reading and the verdict.

        Args:
            args: The agent's validated arguments for draft_matter.
                Required.
            adverse: The parties on the other side, without repeats.
                Required.
            found: The findings from the run's own searches. Required.

        Returns:
            The draft, showing the stricter of the agent's verdict and
            the checks'.
        """
        # log.debug("Takes the agent's arguments, which the caller must give")
        args = required(args=args)
        # log.debug("Takes the adverse parties, which the caller must give")
        adverse = required(adverse=adverse)
        # log.debug("Takes the findings, which the caller must give")
        found = required(found=found)
        # log.debug("Takes the verdict the findings alone support")
        checks = verdict(found)
        # log.debug("Returns the draft, showing the stricter of the two verdicts")
        return Draft(
            id=new_id("D"),
            run_id=self.run_id,
            requester=self.requester.user_id,
            requester_name=self.requester.name,
            created_at=utc_now(),
            client=args.client,
            adverse_parties=tuple(adverse),
            matter_type=args.matter_type,
            timeline=args.timeline,
            summary=args.summary,
            agent_recommendation=args.recommendation,
            agent_reasoning=args.reasoning,
            findings=tuple(found),
            checks_recommendation=checks,
            recommendation=stricter(args.recommendation, checks),
            warnings=self.warnings,
            email=self.email,
            email_sha256=hashlib.sha256(self.email.encode()).hexdigest(),
        )

    # log.debug("Defines request_approval")
    def _submit(self, arguments: dict[str, Any] | None = None) -> ToolReply:
        """Sends this run's draft to an approver; the work ends.

        Args:
            arguments: The model's arguments for request_approval, not
                yet validated. Required.

        Returns:
            The draft's id and its new status, and the word to stop.
        """
        # log.debug("Takes the arguments, which the caller must give")
        arguments = required(arguments=arguments)
        # log.debug("Validates the arguments")
        args = SubmitArgs.model_validate(arguments)
        # log.debug("Moves the draft to pending; the book refuses another run's")
        record = self.drafts.submit(args.draft_id, run_id=self.run_id, note=args.note)
        # log.debug("Remembers that the work is done")
        self.submitted = True
        # log.debug("Tells the model it is finished")
        return ToolReply(
            True, {DRAFT_ID_KEY: record.draft.id, "status": record.status, NEXT: "stop"}
        )

    # log.debug("Defines open_matter, which the gate always refuses for the agent")
    def _open(self, arguments: dict[str, Any] | None = None) -> ToolReply:
        """Tries to open a matter as the agent; the gate refuses it.

        Args:
            arguments: The model's arguments for open_matter, not yet
                validated. Required.

        Returns:
            The opened matter's number, which only a broken gate would
            give: the gate raises for the agent, and the dispatch hands
            the refusal back.
        """
        # log.debug("Takes the arguments, which the caller must give")
        arguments = required(arguments=arguments)
        # log.debug("Validates the arguments")
        args = OpenArgs.model_validate(arguments)
        # log.debug("Counts the attempt, which the evaluation reports")
        self.open_attempts += 1
        # log.debug("Asks the gate as the agent; it raises, and the refusal is returned")
        matter = self.drafts.open(args.draft_id, actor=self.agent)
        # log.debug("Returns the matter; reached only if the gate were broken")
        return ToolReply(True, {"matter": matter.number})

    # log.debug("Defines a refusal reply")
    def _refuse(self, message: str | None = None) -> ToolReply:
        """Returns a refusal with the message.

        Args:
            message: Why the call was refused, for the model to read.
                Required.

        Returns:
            A failed reply carrying the message, with the audit code
            for a refusal.
        """
        # log.debug("Takes the message, which the caller must give")
        message = required(message=message)
        # log.debug("Returns it")
        return ToolReply(False, {ERROR: message}, REFUSED)


# log.debug("Defines the parties without repeats")
def unique(names: list[str] | None = None) -> list[str]:
    """Returns the names in order, without later repeats.

    Args:
        names: Party names as the agent wrote them. Required.

    Returns:
        The names in their first order, each plain form kept once, in
        its first spelling.
    """
    # log.debug("Takes the names, which the caller must give")
    names = required(names=names)
    # log.debug("Starts the plain forms seen")
    seen: set[str] = set()
    # log.debug("Starts the result")
    out: list[str] = []
    # log.debug("Keeps each name whose plain form is new")
    for name in names:
        # log.debug("Skips a repeat")
        if normalize(name) in seen:
            # log.debug("Moves on")
            continue
        # log.debug("Remembers its plain form")
        seen.add(normalize(name))
        # log.debug("Keeps it")
        out.append(name)
    # log.debug("Returns the names")
    return out
