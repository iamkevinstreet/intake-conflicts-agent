########################################################################
#                                                                      #
#                    backend/tests/test_tracing.py                     #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-07
Last modified on:  2026-11-07

Tests the spans of an intake run: one invoke_agent span holding every
model call and every tool call, each tool call saying whether it worked,
and the gate's refusal recorded by its audit code.
"""

########################################################################
#                                                                      #
#                               Imports                                #
#                                                                      #
########################################################################
# Standard library
from __future__ import annotations

# Third-party
from kds.logs import get_logger
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

# Local
from intake_agent.config import AppSettings
from intake_agent.core.store import Store
from support import CONFLICT_EMAIL, REQUESTER, call, good_turns, scripted, service, submit, turn

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
# log.debug("Names the agent's span")
AGENT = "invoke_agent intake"


########################################################################
#                                                                      #
#                            Tracing tests                             #
#                                                                      #
########################################################################
# log.debug("Defines a span's parent's id")
def _parent(span: ReadableSpan | None = None) -> int | None:
    """Returns the id of the span's parent.

    Args:
        span: The span.

    Returns:
        The parent's id, or None for a span that starts its trace.
    """
    # log.debug("Returns the parent's id")
    return span.parent.span_id if span and span.parent else None


# log.debug("Defines a span's own id")
def _own(span: ReadableSpan | None = None) -> int | None:
    """Returns the span's id.

    Args:
        span: The span.

    Returns:
        Its id, or None without a context.
    """
    # log.debug("Returns the id from the span's context")
    return span.context.span_id if span and span.context else None


# log.debug("Defines a span's attributes")
def _attrs(span: ReadableSpan | None = None) -> dict[str, object]:
    """Returns the span's attributes.

    Args:
        span: The span.

    Returns:
        Its attributes by name; empty without any.
    """
    # log.debug("Returns them as a plain table")
    return dict(span.attributes or {}) if span else {}


# log.debug("Defines the test of a good run's spans")
def test_a_run_is_one_agent_span_holding_its_calls(
    settings: AppSettings, store: Store, spans: InMemorySpanExporter
) -> None:
    """Every model and tool call sits inside the agent's span.

    Args:
        settings: The test's settings, from conftest.
        store: The seeded firm database, from conftest.
        spans: The spans this test records.
    """
    # log.debug("Runs a good intake")
    service(settings, store, scripted(settings, *good_turns(), responder=submit)).run(
        CONFLICT_EMAIL, REQUESTER
    )
    # log.debug("Takes the spans")
    finished = spans.get_finished_spans()
    # log.debug("Takes the agent's span")
    (agent,) = [s for s in finished if s.name == AGENT]
    # log.debug("Lists the tool calls, in order")
    tools = [s.name for s in finished if s.name.startswith("execute_tool")]
    # log.debug("Checks the four tools ran, in order")
    assert tools == [
        "execute_tool search_adverse_parties",
        "execute_tool search_clients",
        "execute_tool draft_matter",
        "execute_tool request_approval",
    ]
    # log.debug("Checks every other span of the run sits inside the agent's span")
    assert {_parent(s) for s in finished if s is not agent} == {_own(agent)}
    # log.debug("Checks the run's outcome and counts are on its span")
    assert {k: _attrs(agent)[k] for k in ("agent.outcome", "agent.tool_calls")} == {
        "agent.outcome": "submitted",
        "agent.tool_calls": 4,
    }


# log.debug("Defines the test that the gate's refusal is on the tool's span")
def test_the_gates_refusal_is_on_the_tools_span(
    settings: AppSettings, store: Store, spans: InMemorySpanExporter
) -> None:
    """open_matter is refused, and its span says so by audit code.

    Args:
        settings: The test's settings, from conftest.
        store: The seeded firm database, from conftest.
        spans: The spans this test records.
    """
    # log.debug("Runs an intake whose model tries to open a matter")
    service(
        settings,
        store,
        scripted(settings, turn(call("c1", "open_matter", draft_id="d1")), "Done."),
    ).run(CONFLICT_EMAIL, REQUESTER)
    # log.debug("Takes the open_matter span")
    (opened,) = [s for s in spans.get_finished_spans() if s.name == "execute_tool open_matter"]
    # log.debug("Checks it did not work, and why")
    assert _attrs(opened)["tool.ok"] is False and _attrs(opened)["tool.code"]
