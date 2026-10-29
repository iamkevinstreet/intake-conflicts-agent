########################################################################
#              backend/src/intake_agent/core/searches.py               #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Runs the two search tools for one run and remembers what each found.
Both searches only read, through `Directory`, and retry a timed-out read
a bounded number of times before reporting failure. The memory of every
search is what draft_matter checks before it saves a draft, and the
findings it saves come from these searches alone, so the agent cannot
leave a match out or change its severity.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Third-party
from kds.args import required
from kds.logs import get_logger

# Local
from intake_agent.config import AppSettings
from intake_agent.core import prompt
from intake_agent.core.conflicts import findings, search_adverse, search_clients
from intake_agent.core.firm import Directory
from intake_agent.core.models import Finding, Match, SearchArgs, ToolReply
from intake_agent.core.names import normalize
from intake_agent.core.store import StoreTimeoutError

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)

########################################################################
#                           Local constants                            #
########################################################################
# log.debug("Names the error key every refusal carries")
ERROR = prompt.ERROR_KEY
# log.debug("Names the key that tells the model what to do next")
NEXT = prompt.NEXT_KEY


########################################################################
#                             Search tools                             #
########################################################################
# log.debug("Defines what one search left behind")
@dataclass(frozen=True)
class SearchResult:
    """Whether a search worked, and what it found."""

    # log.debug("Holds whether the read succeeded")
    ok: bool
    # log.debug("Holds the matches")
    matches: tuple[Match, ...] = ()


# log.debug("Defines the search tools a toolbox has, and their memory")
class SearchTools:
    """The two search tools, and what each search of the run found.

    The toolbox that inherits these holds the attributes declared
    here: the firm's records, the settings, the wait between retries
    and the memory of every search.
    """

    # log.debug("Declares the read-only view of the firm the searches read")
    directory: Directory
    # log.debug("Declares the settings that give the thresholds and the retries")
    settings: AppSettings
    # log.debug("Declares how to wait between retries")
    sleep: Callable[[float], None]
    # log.debug("Declares every search so far, by tool and plain name")
    searched: dict[tuple[str, str], SearchResult]

    # log.debug("Defines whether any search failed")
    @property
    def search_failed(self) -> bool:
        """Returns True if any search's last attempt failed.

        Returns:
            True when a search of this run could not read the firm's
            records, even after its retries.
        """
        # log.debug("Checks every search")
        return any(not result.ok for result in self.searched.values())

    # log.debug("Defines search_clients")
    def _search_clients(self, arguments: dict[str, Any] | None = None) -> ToolReply:
        """Searches the clients for the given name.

        Args:
            arguments: The model's arguments for the tool, not yet
                validated. Required.

        Returns:
            The matches, or why the search failed.
        """
        # log.debug("Takes the arguments, which the caller must give")
        arguments = required(arguments=arguments)
        # log.debug("Searches with the client reader and matcher")
        return self._search(
            prompt.SEARCH_CLIENTS,
            SearchArgs.model_validate(arguments).name,
            lambda name: search_clients(self.directory.clients(), name, **self._limits()),
        )

    # log.debug("Defines search_adverse_parties")
    def _search_adverse(self, arguments: dict[str, Any] | None = None) -> ToolReply:
        """Searches the adverse parties for the given name.

        Args:
            arguments: The model's arguments for the tool, not yet
                validated. Required.

        Returns:
            The matches, or why the search failed.
        """
        # log.debug("Takes the arguments, which the caller must give")
        arguments = required(arguments=arguments)
        # log.debug("Searches with the adverse reader and matcher")
        return self._search(
            prompt.SEARCH_ADVERSE,
            SearchArgs.model_validate(arguments).name,
            lambda name: search_adverse(self.directory.adverse_parties(), name, **self._limits()),
        )

    # log.debug("Defines the search both tools share: retries, then the record")
    def _search(
        self,
        tool: str | None = None,
        name: str | None = None,
        run: Callable[[str], list[Match]] | None = None,
    ) -> ToolReply:
        """Runs a search with bounded retries and remembers its result.

        Args:
            tool: The search tool's name, which the memory files the
                result under. Required.
            name: The name to look for. Required.
            run: Reads the firm's records and matches the name against
                them. Required.

        Returns:
            The query and its matches, or, after the last retry, an
            error telling the model to stop rather than draft.
        """
        # log.debug("Takes the tool's name, which the caller must give")
        tool = required(tool=tool)
        # log.debug("Takes the name to look for, which the caller must give")
        name = required(name=name)
        # log.debug("Takes the search to run, which the caller must give")
        run = required(run=run)
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
        """Returns the band thresholds and match limit from settings.

        Returns:
            The likely and possible thresholds and the most matches,
            named as the search functions take them.
        """
        # log.debug("Returns them")
        return {
            "likely": self.settings.match_likely,
            "possible": self.settings.match_possible,
            "limit": self.settings.match_limit,
        }

    # log.debug("Defines the record of one needed search")
    def _result(self, tool: str | None = None, name: str | None = None) -> SearchResult:
        """Returns the search's result; one not made counts as fine.

        Args:
            tool: The search tool's name. Required.
            name: The name searched for, as the draft names it.
                Required.

        Returns:
            What the search found, or an empty success when it was
            never made.
        """
        # log.debug("Takes the tool's name, which the caller must give")
        tool = required(tool=tool)
        # log.debug("Takes the name searched for, which the caller must give")
        name = required(name=name)
        # log.debug("Returns the remembered result, or an empty success")
        return self.searched.get((tool, normalize(name)), SearchResult(True))

    # log.debug("Defines the check for a search never made")
    def _unsearched(self, tool: str | None = None, name: str | None = None) -> bool:
        """Returns True if this search was never made in this run.

        Args:
            tool: The search tool's name. Required.
            name: The name to look for, as the draft names it.
                Required.

        Returns:
            True when no search of this run used the tool on the name,
            in any spelling with the same plain form.
        """
        # log.debug("Takes the tool's name, which the caller must give")
        tool = required(tool=tool)
        # log.debug("Takes the name to look for, which the caller must give")
        name = required(name=name)
        # log.debug("Checks the memory")
        return (tool, normalize(name)) not in self.searched

    # log.debug("Defines the findings for the draft's parties")
    def _findings(
        self, client: str | None = None, adverse: list[str] | None = None
    ) -> list[Finding]:
        """Returns the client's findings, then each adverse party's.

        Args:
            client: The prospective client, as the draft names it.
                Required.
            adverse: The parties on the other side, without repeats.
                Required.

        Returns:
            Every match the run's searches found for these parties,
            each judged by the conflicts rules.
        """
        # log.debug("Takes the client, which the caller must give")
        client = required(client=client)
        # log.debug("Takes the adverse parties, which the caller must give")
        adverse = required(adverse=adverse)
        # log.debug("Judges the client against the parties the firm is against")
        found = findings(client, "client", self._result(prompt.SEARCH_ADVERSE, client).matches)
        # log.debug("Judges each adverse party against the firm's clients")
        for party in adverse:
            # log.debug("Adds that party's findings")
            found += findings(party, "adverse", self._result(prompt.SEARCH_CLIENTS, party).matches)
        # log.debug("Returns them")
        return found
