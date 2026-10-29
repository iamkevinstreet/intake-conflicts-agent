########################################################################
#                     backend/tests/test_tools.py                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Tests the five tools: the draft guard, findings from searches, scope,
retries and the audit.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

import json

# Third-party
import pytest
from kds.args import required
from kds.logs import get_logger

# Local
from intake_agent.config import AppSettings
from intake_agent.core.audit import RunLog
from intake_agent.core.drafts import DraftBook
from intake_agent.core.firm import SqliteDirectory
from intake_agent.core.store import Store
from intake_agent.core.tools import Toolbox, unique
from intake_agent.evals.scenarios import TimeoutDirectory
from support import CONFLICT_EMAIL, REQUESTER, draft_args

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)


########################################################################
#                              Tool tests                              #
########################################################################
# log.debug("Defines a toolbox for one run")
@pytest.fixture
def box(store: Store, settings: AppSettings) -> Toolbox:
    """A toolbox for run R-test, with its run record opened.

    Args:
        store: The seeded firm database, from conftest.
        settings: The test's settings, from conftest.

    Returns:
        The toolbox, acting for the requester, with no waits between
        retries.
    """
    # log.debug("Opens the audit log")
    runlog = RunLog(store)
    # log.debug("Opens the run record the tool calls belong to")
    runlog.start("R-test", actor=REQUESTER, email=CONFLICT_EMAIL, model="fake-model")
    # log.debug("Returns the toolbox")
    return Toolbox(
        run_id="R-test",
        requester=REQUESTER,
        email=CONFLICT_EMAIL,
        warnings=(),
        directory=SqliteDirectory(store),
        drafts=DraftBook(store, min_reason_chars=10),
        runlog=runlog,
        settings=settings,
        sleep=lambda _: None,
    )


# log.debug("Defines the searches a valid draft needs")
def _search_both(box: Toolbox | None = None) -> None:
    """Searches the client and the adverse party of the default draft.

    Args:
        box: The toolbox to search with. Required.
    """
    # log.debug("Takes the toolbox, which the caller must give")
    box = required(box=box)
    # log.debug("Searches the client among adverse parties")
    box.call("search_adverse_parties", {"name": "Falcon Ridge Supply LLC"}, step=1)
    # log.debug("Searches the adverse party among clients")
    box.call("search_clients", {"name": "Ironwood Builders Inc."}, step=1)


# log.debug("Defines the search test")
def test_search_returns_matches_with_bands(box: Toolbox) -> None:
    """A planted client comes back exact, with its status.

    Args:
        box: A toolbox for one run on the seeded firm.
    """
    # log.debug("Searches both parties")
    reply = box.call("search_clients", {"name": "Ironwood Builders, Inc."}, step=1)
    # log.debug("Checks the match")
    assert [(m["name"], m["band"], m["status"]) for m in reply.payload["matches"]] == [
        ("Ironwood Builders Inc.", "exact", "current")
    ]


# log.debug("Defines the draft-guard test")
def test_draft_needs_every_search_first(box: Toolbox) -> None:
    """Drafting before searching is refused, naming what is missing.

    Args:
        box: A toolbox for one run on the seeded firm.
    """
    # log.debug("Drafts with no searches")
    reply = box.call("draft_matter", draft_args(), step=1)
    # log.debug("Checks the refusal lists both searches")
    assert (reply.ok, reply.payload["missing"]) == (
        False,
        [
            "search_adverse_parties: Falcon Ridge Supply LLC",
            "search_clients: Ironwood Builders Inc.",
        ],
    )


# log.debug("Defines the test that findings come from the searches, not the model")
def test_the_agent_cannot_hide_a_conflict(box: Toolbox) -> None:
    """The agent says clear; the approver still sees the conflict.

    Args:
        box: A toolbox for one run on the seeded firm.
    """
    # log.debug("Searches both parties")
    _search_both(box)
    # log.debug("Drafts with the agent claiming there is nothing")
    reply = box.call("draft_matter", draft_args(recommendation="clear"), step=2)
    # log.debug("Reads the saved draft")
    draft = box.drafts.get(reply.payload["draft_id"]).draft
    # log.debug("Checks the finding and both verdicts")
    assert (
        [f.match.name for f in draft.findings],
        draft.agent_recommendation,
        draft.checks_recommendation,
        draft.recommendation,
    ) == (["Ironwood Builders Inc."], "clear", "conflict", "conflict")


# log.debug("Defines the one-draft test")
def test_one_draft_per_run(box: Toolbox) -> None:
    """A second draft is refused and points to the first.

    Args:
        box: A toolbox for one run on the seeded firm.
    """
    # log.debug("Searches and drafts")
    _search_both(box)
    # log.debug("Saves the first draft")
    first = box.call("draft_matter", draft_args(), step=2)
    # log.debug("Tries a second")
    second = box.call("draft_matter", draft_args(), step=3)
    # log.debug("Checks it was refused")
    assert not second.ok and first.payload["draft_id"] in second.payload["error"]


# log.debug("Defines the repeated-party test")
def test_repeated_parties_are_dropped() -> None:
    """Two spellings of one party count once, the first kept."""
    # log.debug("Checks the result")
    assert unique(["Acme Logistic Inc.", "ACME LOGISTIC", "Tobias Renner"]) == [
        "Acme Logistic Inc.",
        "Tobias Renner",
    ]


# log.debug("Defines the request-approval scope test")
def test_request_approval_only_for_this_runs_draft(box: Toolbox, store: Store) -> None:
    """Another run's draft id is refused.

    Args:
        box: A toolbox for one run on the seeded firm.
        store: The seeded firm database, from conftest.
    """
    # log.debug("Searches and drafts in this run")
    _search_both(box)
    # log.debug("Saves the draft")
    draft_id = box.call("draft_matter", draft_args(), step=2).payload["draft_id"]
    # log.debug("Opens another run's record")
    box.runlog.start("R-other", actor=REQUESTER, email=CONFLICT_EMAIL, model="fake-model")
    # log.debug("Pretends to be that run, with the same tools")
    box.run_id = "R-other"
    # log.debug("Tries to submit this run's draft from the other run")
    reply = box.call("request_approval", {"draft_id": draft_id}, step=3)
    # log.debug("Checks the refusal")
    assert (reply.ok, reply.code) == (False, "refused")


# log.debug("Defines the bad-arguments test")
@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("search_clients", {}),
        ("search_clients", {"name": "x", "limit": 500}),
        ("draft_matter", draft_args(recommendation="maybe")),
        ("request_approval", {"draft_id": "../../etc"}),
    ],
)
def test_invalid_arguments_are_refused(
    box: Toolbox, tool: str, arguments: dict[str, object]
) -> None:
    """Missing, unknown or malformed arguments never reach the tool.

    Args:
        box: A toolbox for one run on the seeded firm.
        tool: The tool to call.
        arguments: Arguments the tool must refuse.
    """
    # log.debug("Calls the tool")
    reply = box.call(tool, arguments, step=1)
    # log.debug("Checks the refusal")
    assert (reply.ok, reply.code) == (False, "invalid")


# log.debug("Defines the unknown-tool test")
def test_unknown_tool(box: Toolbox) -> None:
    """A tool that does not exist is refused, not raised.

    Args:
        box: A toolbox for one run on the seeded firm.
    """
    # log.debug("Calls it")
    reply = box.call("delete_client", {"name": "x"}, step=1)
    # log.debug("Checks the refusal")
    assert (reply.ok, reply.code) == (False, "unknown_tool")


# log.debug("Defines the agent's open_matter test")
def test_open_matter_is_refused_for_the_agent(box: Toolbox) -> None:
    """The agent's call reaches the gate and is refused.

    Args:
        box: A toolbox for one run on the seeded firm.
    """
    # log.debug("Searches, drafts and submits")
    _search_both(box)
    # log.debug("Saves the draft")
    draft_id = box.call("draft_matter", draft_args(), step=2).payload["draft_id"]
    # log.debug("Tries to open it")
    reply = box.call("open_matter", {"draft_id": draft_id}, step=3)
    # log.debug("Checks the refusal and the count")
    assert (reply.ok, reply.code, box.open_attempts) == (False, "refused", 1)


# log.debug("Defines the timeout test")
def test_a_timed_out_search_retries_then_blocks_the_draft(box: Toolbox) -> None:
    """Three tries with growing waits, then no draft can be saved.

    Args:
        box: A toolbox for one run on the seeded firm.
    """
    # log.debug("Records each wait")
    waits: list[float] = []
    # log.debug("Swaps in a database that never answers and the recorder")
    box.directory, box.sleep = TimeoutDirectory(), waits.append
    # log.debug("Searches both parties")
    _search_both(box)
    # log.debug("Tries to draft")
    reply = box.call("draft_matter", draft_args(), step=2)
    # log.debug("Checks the waits, and that the draft names both failed searches")
    assert (waits, len(reply.payload["failed"]), box.search_failed) == ([0.2, 0.4] * 2, 2, True)


# log.debug("Defines the audit test")
def test_every_call_is_audited_with_redaction(box: Toolbox, store: Store) -> None:
    """Arguments are stored redacted; the result as a hash.

    Args:
        box: A toolbox for one run on the seeded firm.
        store: The seeded firm database, from conftest.
    """
    # log.debug("Searches with an email address in the name")
    box.call("search_clients", {"name": "dana@example.com"}, step=1)
    # log.debug("Reads the run's tool calls")
    detail = RunLog(store).detail("R-test")
    # log.debug("Checks the call was recorded, redacted, with a 64-character hash")
    assert detail is not None and [
        (c.tool, c.arguments, len(c.result_sha256)) for c in detail.tool_calls
    ] == [("search_clients", {"name": "[EMAIL]"}, 64)]


# log.debug("Defines the search-is-read-only test")
def test_searches_write_nothing(box: Toolbox, store: Store) -> None:
    """The firm's tables are byte for byte the same after searching.

    Args:
        box: A toolbox for one run on the seeded firm.
        store: The seeded firm database, from conftest.
    """

    # log.debug("Defines a dump of the three firm tables")
    def dump() -> str:
        """Returns every firm row as JSON.

        Returns:
            The clients, matters and adverse parties, row by row.
        """
        # log.debug("Reads the tables")
        with store.connect() as connection:
            # log.debug("Returns them")
            return json.dumps(
                [
                    [list(r) for r in connection.execute(query)]
                    for query in (
                        "SELECT * FROM clients",
                        "SELECT * FROM matters",
                        "SELECT * FROM adverse_parties",
                    )
                ]
            )

    # log.debug("Takes the before picture")
    before = dump()
    # log.debug("Searches both parties")
    _search_both(box)
    # log.debug("Checks nothing changed")
    assert dump() == before
