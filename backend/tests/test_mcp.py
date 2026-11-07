########################################################################
#                                                                      #
#                      backend/tests/test_mcp.py                       #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-07
Last modified on:  2026-11-07

Tests the MCP server through a real MCP client in process: the tools it
offers, never open_matter; a client that searches, drafts and sends a
draft for approval, and still cannot open the matter; the toolbox's
refusals reaching the client as errors; and how runs end.
"""

########################################################################
#                                                                      #
#                               Imports                                #
#                                                                      #
########################################################################
# Standard library
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

# Third-party
import anyio
import pytest
from kds.args import required
from kds.logs import get_logger
from mcp import Client

# Local
from intake_agent.api.state import Records, open_records
from intake_agent.config import AppSettings
from intake_agent.core.refusals import GateError
from intake_agent.mcp_server.runs import SERVER_STOPPED, McpRuns
from intake_agent.mcp_server.server import NOT_OPEN, build_server
from support import CONFLICT_EMAIL, draft_args

########################################################################
#                                                                      #
#                           Global constants                           #
#                                                                      #
########################################################################
log = get_logger(__name__)

########################################################################
#                                                                      #
#                           Local constants                            #
#                                                                      #
########################################################################
# log.debug("Lists the tools a client sees: the agent's, without open_matter")
TOOLS = {
    "start_intake",
    "search_clients",
    "search_adverse_parties",
    "draft_matter",
    "request_approval",
    "end_intake",
}
# log.debug("Sets the client of the conflict email")
CLIENT = "Falcon Ridge Supply LLC"
# log.debug("Sets the party on the other side, a current client of the firm")
ADVERSE = "Ironwood Builders Inc."


########################################################################
#                                                                      #
#                              MCP tests                               #
#                                                                      #
########################################################################
# log.debug("Defines how a test talks to the server in process")
def _talk(
    runs: McpRuns | None = None, talk: Callable[[Client], Awaitable[Any]] | None = None
) -> Any:
    """Builds the server on the runs and returns what `talk` gets.

    Args:
        runs: The runs the client opens. Required.
        talk: What the client does, given a connected client.
            Required.

    Returns:
        What `talk` returned.
    """
    # log.debug("Takes the runs, which the caller must give")
    runs = required(runs=runs)
    # log.debug("Takes what the client does, which the caller must give")
    talk = required(talk=talk)
    # log.debug("Builds the server on them")
    server = build_server(runs)

    # log.debug("Defines the conversation")
    async def run() -> Any:
        """Connects in process and lets the test talk.

        Returns:
            What `talk` returned.
        """
        # log.debug("Connects a client to the server in process")
        async with Client(server) as client:
            # log.debug("Returns what the test's talk returns")
            return await talk(client)

    # log.debug("Runs the conversation to its end")
    return anyio.run(run)


# log.debug("Defines the records and runs one test works on")
@pytest.fixture
def opened(settings: AppSettings) -> tuple[Records, McpRuns]:
    """Opens the seeded database and an MCP server's runs on it.

    Args:
        settings: The test's settings, from conftest.

    Returns:
        The records, and the runs a client opens on them.
    """
    # log.debug("Opens and seeds the database")
    records = open_records(settings)
    # log.debug("Returns them, with the runs")
    return records, McpRuns(records, settings)


# log.debug("Defines the conversation of a client that does the whole intake")
async def _whole_intake(client: Client | None = None) -> tuple[str, Any]:
    """Starts a run, searches both parties, drafts and sends the draft.

    Args:
        client: The connected client. Required.

    Returns:
        The run's id, and what request_approval returned.
    """
    # log.debug("Takes the client, which the caller must give")
    client = required(client=client)
    # log.debug("Starts the run")
    started = await client.call_tool("start_intake", {"email": CONFLICT_EMAIL})
    # log.debug("Reads the run's id")
    run_id = started.structured_content["run_id"]
    # log.debug("Checks the client against the parties the firm has opposed")
    await client.call_tool("search_adverse_parties", {"run_id": run_id, "name": CLIENT})
    # log.debug("Checks the other side against the firm's clients")
    await client.call_tool("search_clients", {"run_id": run_id, "name": ADVERSE})
    # log.debug("Drafts the matter")
    await client.call_tool("draft_matter", {"run_id": run_id, "draft": draft_args()})
    # log.debug("Sends the draft for approval")
    return run_id, await client.call_tool("request_approval", {"run_id": run_id})


# log.debug("Defines the test of the tools a client sees")
def test_the_tools_are_the_agents_without_open_matter(
    opened: tuple[Records, McpRuns],
) -> None:
    """Six tools, searches marked read-only, and no open_matter.

    Args:
        opened: The records and the runs, from the fixture.
    """
    # log.debug("Lists the tools")
    listed = _talk(opened[1], lambda c: c.list_tools())
    # log.debug("Finds each tool by name")
    named = {tool.name: tool for tool in listed.tools}
    # log.debug("Checks the six tools, and only those")
    assert set(named) == TOOLS
    # log.debug("Checks only the searches are marked read-only, and nothing destructive")
    assert {n for n, t in named.items() if t.annotations.read_only_hint} == {
        "search_clients",
        "search_adverse_parties",
    } and not any(t.annotations.destructive_hint for t in named.values())


# log.debug("Defines the test of a whole intake through MCP")
def test_a_client_sends_a_draft_but_cannot_open_the_matter(
    opened: tuple[Records, McpRuns],
) -> None:
    """The draft waits for an approver, and the gate refuses the client.

    Args:
        opened: The records and the runs, from the fixture.
    """
    # log.debug("Takes the records and the runs")
    records, runs = opened
    # log.debug("Does the whole intake")
    run_id, sent = _talk(runs, _whole_intake)
    # log.debug("Checks the draft went to an approver")
    assert (sent.is_error, sent.structured_content["status"]) == (False, "pending")
    # log.debug("Reads the run's audit record")
    record = records.runlog.run(run_id)
    # log.debug("Checks it ended submitted, with every call recorded")
    assert record is not None and (record.outcome, record.tool_calls) == ("submitted", 4)
    # log.debug("Checks the gate refuses the client's identity")
    with pytest.raises(GateError):
        # log.debug("Tries to open the matter as the client")
        records.drafts.open(sent.structured_content["draft_id"], actor=runs.requester)


# log.debug("Defines the test that the toolbox's refusals reach the client")
def test_a_draft_naming_an_unsearched_party_is_refused(
    opened: tuple[Records, McpRuns],
) -> None:
    """Drafting before searching is an error the client's model reads.

    Args:
        opened: The records and the runs, from the fixture.
    """

    # log.debug("Defines a client that drafts without searching")
    async def hasty(client: Client | None = None) -> Any:
        """Starts a run and drafts at once.

        Args:
            client: The connected client. Required.

        Returns:
            What draft_matter returned.
        """
        # log.debug("Takes the client, which the caller must give")
        client = required(client=client)
        # log.debug("Starts the run")
        started = await client.call_tool("start_intake", {"email": CONFLICT_EMAIL})
        # log.debug("Drafts with nothing searched")
        return await client.call_tool(
            "draft_matter", {"run_id": started.structured_content["run_id"], "draft": draft_args()}
        )

    # log.debug("Runs it")
    drafted = _talk(opened[1], hasty)
    # log.debug("Checks it was refused, saying the party was not searched")
    assert drafted.is_error and "search" in drafted.content[0].text


# log.debug("Defines the test of ending a run")
def test_an_ended_run_records_why_and_takes_no_more_calls(
    opened: tuple[Records, McpRuns],
) -> None:
    """end_intake closes the run as no_draft; later calls are refused.

    Args:
        opened: The records and the runs, from the fixture.
    """

    # log.debug("Defines a client that ends a run, then searches on it")
    async def ends(client: Client | None = None) -> tuple[str, Any, Any]:
        """Starts a run, ends it, and tries to use it again.

        Args:
            client: The connected client. Required.

        Returns:
            The run's id, end_intake's result and the late search's.
        """
        # log.debug("Takes the client, which the caller must give")
        client = required(client=client)
        # log.debug("Starts the run")
        started = await client.call_tool("start_intake", {"email": CONFLICT_EMAIL})
        # log.debug("Reads its id")
        run_id = started.structured_content["run_id"]
        # log.debug("Ends it")
        ended = await client.call_tool("end_intake", {"run_id": run_id, "reason": "not an intake"})
        # log.debug("Returns what ending and a late search returned")
        return (
            run_id,
            ended,
            await client.call_tool("search_clients", {"run_id": run_id, "name": ADVERSE}),
        )

    # log.debug("Runs it")
    run_id, ended, late = _talk(opened[1], ends)
    # log.debug("Reads the run's audit record")
    record = opened[0].runlog.run(run_id)
    # log.debug("Checks the client and the audit log agree on how it ended, and why")
    assert record is not None and (ended.structured_content["outcome"], record.reason) == (
        record.outcome,
        "not an intake",
    )
    # log.debug("Checks the late call was refused")
    assert late.is_error and NOT_OPEN in late.content[0].text


# log.debug("Defines the test that open runs end when the server stops")
def test_runs_left_open_end_when_the_server_stops(opened: tuple[Records, McpRuns]) -> None:
    """A started run is closed as incomplete, saying the server stopped.

    Args:
        opened: The records and the runs, from the fixture.
    """
    # log.debug("Takes the records and the runs")
    records, runs = opened
    # log.debug("Starts a run and leaves it open")
    run_id = runs.start(CONFLICT_EMAIL).toolbox.run_id
    # log.debug("Stops the server, ending what is open")
    assert runs.close_all() == 1
    # log.debug("Reads the run's audit record")
    record = records.runlog.run(run_id)
    # log.debug("Checks it ended incomplete, saying why")
    assert record is not None and (record.outcome, record.reason) == ("incomplete", SERVER_STOPPED)


# log.debug("Defines the test of the limit on open runs")
def test_too_many_open_runs_are_refused(opened: tuple[Records, McpRuns]) -> None:
    """Past the limit, start_intake is an error until one ends.

    Args:
        opened: The records and the runs, from the fixture.
    """

    # log.debug("Defines a client that starts one run more than allowed")
    async def greedy(client: Client | None = None) -> list[Any]:
        """Starts four runs.

        Args:
            client: The connected client. Required.

        Returns:
            What each start returned.
        """
        # log.debug("Takes the client, which the caller must give")
        client = required(client=client)
        # log.debug("Starts them, one by one")
        return [
            await client.call_tool("start_intake", {"email": CONFLICT_EMAIL}) for _ in range(4)
        ]

    # log.debug("Runs it")
    started = _talk(opened[1], greedy)
    # log.debug("Checks the first three opened and the fourth was refused")
    assert [s.is_error for s in started] == [False, False, False, True]
