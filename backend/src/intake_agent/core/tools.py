########################################################################
#                backend/src/intake_agent/core/tools.py                #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           The five tools for one run: read-only searches,  #
#                     one checked draft, and a gated open.             #
########################################################################
"""The agent's five tools, and the rules that hold whatever it asks.

- Both searches only read, through `Directory`, and retry a timed-out
  read a bounded number of times before reporting failure.
- draft_matter writes one draft per run, only after every party on it
  was searched, and computes the findings itself from those searches:
  the agent cannot leave a match out or change its severity.
- request_approval sends only this run's own draft.
- open_matter goes through the same gate as the approver's button,
  with the requester's role only, so it is always refused.

Every call is validated, timed and written to the audit log, and none
raises: refusals and failures go back to the model as JSON, so it can
read why and stop or correct itself.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from kds.logs import get_logger
from pydantic import ValidationError

from intake_agent.config import AppSettings
from intake_agent.core import prompt
from intake_agent.core.audit import RunLog
from intake_agent.core.conflicts import (
    findings,
    search_adverse,
    search_clients,
    stricter,
    verdict,
)
from intake_agent.core.drafts import DraftBook, DraftError
from intake_agent.core.firm import Directory
from intake_agent.core.models import (
    Actor,
    Draft,
    DraftArgs,
    Finding,
    Match,
    OpenArgs,
    SearchArgs,
    SubmitArgs,
)
from intake_agent.core.names import normalize
from intake_agent.core.store import StoreTimeoutError, new_id, utc_now

# Module constants
log = get_logger(__name__)
# log.debug("Sets the milliseconds in a second")
MS = 1000
# log.debug("Names the error key every refusal carries")
ERROR = prompt.ERROR_KEY
# log.debug("Names the key that tells the model what to do next")
NEXT = "next"
# log.debug("Names the key that carries a draft id")
DRAFT_ID_KEY = prompt.DRAFT_ID_KEY
# log.debug("Names the audit code for a refused call")
REFUSED = "refused"


# log.debug("Defines what a tool call returns")
@dataclass(frozen=True)
class ToolReply:
    """If the call worked, what the model is told, the audit code."""

    # log.debug("Holds whether the call did what was asked")
    ok: bool
    # log.debug("Holds the JSON the model reads")
    payload: dict[str, Any]
    # log.debug("Holds a short code for the audit when it did not")
    code: str = ""


# log.debug("Defines what one search left behind")
@dataclass(frozen=True)
class SearchResult:
    """Whether a search worked, and what it found."""

    # log.debug("Holds whether the read succeeded")
    ok: bool
    # log.debug("Holds the matches")
    matches: tuple[Match, ...] = ()


# log.debug("Defines the toolbox one run uses")
@dataclass
class Toolbox:
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
        """Return the requester's identity, requester role only."""
        # log.debug("Returns it, so a user with both roles still cannot open")
        return Actor(
            user_id=self.requester.user_id,
            name=self.requester.name,
            roles=frozenset({"requester"}),
        )

    # log.debug("Defines whether any search failed")
    @property
    def search_failed(self) -> bool:
        """Return True if any search's last attempt failed."""
        # log.debug("Checks every search")
        return any(not result.ok for result in self.searched.values())

    # log.debug("Defines one tool call: validate, run, audit, reply")
    def call(self, name: str, arguments: dict[str, Any], *, step: int) -> ToolReply:
        """Run one tool call and record it; never raises."""
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
    def _dispatch(self, name: str, arguments: dict[str, Any]) -> ToolReply:
        """Return the tool's reply, or why it was refused."""
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

    # log.debug("Defines search_clients")
    def _search_clients(self, arguments: dict[str, Any]) -> ToolReply:
        """Search the clients for the given name."""
        # log.debug("Searches with the client reader and matcher")
        return self._search(
            prompt.SEARCH_CLIENTS,
            SearchArgs.model_validate(arguments).name,
            lambda name: search_clients(self.directory.clients(), name, **self._limits()),
        )

    # log.debug("Defines search_adverse_parties")
    def _search_adverse(self, arguments: dict[str, Any]) -> ToolReply:
        """Search the adverse parties for the given name."""
        # log.debug("Searches with the adverse reader and matcher")
        return self._search(
            prompt.SEARCH_ADVERSE,
            SearchArgs.model_validate(arguments).name,
            lambda name: search_adverse(self.directory.adverse_parties(), name, **self._limits()),
        )

    # log.debug("Defines the search both tools share: retries, then the record")
    def _search(self, tool: str, name: str, run: Callable[[str], list[Match]]) -> ToolReply:
        """Run a search with bounded retries and remember its result."""
        # log.debug("Tries the read, then each retry")
        for attempt in range(self.settings.store_retries + 1):
            # log.debug("Reads and matches")
            try:
                # log.debug("Runs the search")
                matches = run(name)
            except StoreTimeoutError:
                # log.debug("Waits before the next try, longer each time: 0.2s, then 0.4s")
                if attempt < self.settings.store_retries:
                    # log.debug("Waits out the backoff")
                    self.sleep(self.settings.store_backoff_s * 2**attempt)
                # log.debug("Tries again, or gives up after the last try")
                continue
            # log.debug("Remembers the search")
            self.searched[(tool, normalize(name))] = SearchResult(True, tuple(matches))
            # log.debug("Returns the matches")
            return ToolReply(
                True,
                {"query": name, "matches": [m.model_dump(exclude_none=True) for m in matches]},
            )
        # log.debug("Remembers that the search failed")
        self.searched[(tool, normalize(name))] = SearchResult(False)
        # log.debug("Tells the model to stop rather than guess")
        return ToolReply(
            False,
            {
                ERROR: "the conflicts database did not answer, after retries",
                NEXT: "do not draft; report that the conflicts check could not be completed",
            },
            "search_failed",
        )

    # log.debug("Defines the thresholds every search uses")
    def _limits(self) -> dict[str, int]:
        """Return the band thresholds and match limit from settings."""
        # log.debug("Returns them")
        return {
            "likely": self.settings.match_likely,
            "possible": self.settings.match_possible,
            "limit": self.settings.match_limit,
        }

    # log.debug("Defines draft_matter")
    def _draft(self, arguments: dict[str, Any]) -> ToolReply:
        """Save the run's one draft, with findings from its searches."""
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

    # log.debug("Defines the record of one needed search")
    def _result(self, tool: str, name: str) -> SearchResult:
        """Return the search's result; one not made counts as fine."""
        # log.debug("Returns the remembered result, or an empty success")
        return self.searched.get((tool, normalize(name)), SearchResult(True))

    # log.debug("Defines the check for a search never made")
    def _unsearched(self, tool: str, name: str) -> bool:
        """Return True if this search was never made in this run."""
        # log.debug("Checks the memory")
        return (tool, normalize(name)) not in self.searched

    # log.debug("Defines the findings for the draft's parties")
    def _findings(self, client: str, adverse: list[str]) -> list[Finding]:
        """Return the client's findings, then each adverse party's."""
        # log.debug("Judges the client against the parties the firm is against")
        found = findings(client, "client", self._result(prompt.SEARCH_ADVERSE, client).matches)
        # log.debug("Judges each adverse party against the firm's clients")
        for party in adverse:
            # log.debug("Adds that party's findings")
            found += findings(party, "adverse", self._result(prompt.SEARCH_CLIENTS, party).matches)
        # log.debug("Returns them")
        return found

    # log.debug("Defines the draft built from the agent's reading and the checks")
    def _build(self, args: DraftArgs, adverse: list[str], found: list[Finding]) -> Draft:
        """Return the draft: the agent's reading and the verdict."""
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
    def _submit(self, arguments: dict[str, Any]) -> ToolReply:
        """Send this run's draft to an approver; the work ends."""
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
    def _open(self, arguments: dict[str, Any]) -> ToolReply:
        """Try to open a matter as the agent; the gate refuses it."""
        # log.debug("Validates the arguments")
        args = OpenArgs.model_validate(arguments)
        # log.debug("Counts the attempt, which the evaluation reports")
        self.open_attempts += 1
        # log.debug("Asks the gate as the agent; it raises, and the refusal is returned")
        matter = self.drafts.open(args.draft_id, actor=self.agent)
        # log.debug("Returns the matter; reached only if the gate were broken")
        return ToolReply(True, {"matter": matter.number})

    # log.debug("Defines a refusal reply")
    def _refuse(self, message: str) -> ToolReply:
        """Return a refusal with the message."""
        # log.debug("Returns it")
        return ToolReply(False, {ERROR: message}, REFUSED)


# log.debug("Defines the parties without repeats")
def unique(names: list[str]) -> list[str]:
    """Return the names in order, without later repeats."""
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
