########################################################################
#                     backend/tests/test_agent.py                      #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           Tests the agent loop and service: limits,        #
#                     outages, timeouts and what is recorded.          #
########################################################################
"""Tests for the agent loop and the service around it."""

from __future__ import annotations

from typing import Any

import anthropic
import httpx2
import pytest
from kds.llm import ModelAdapter, TransientError
from kds.llm.fake import FakeProvider
from kds.logs import get_logger

from intake_agent.config import AppSettings
from intake_agent.core.audit import RunLog
from intake_agent.core.store import Store
from intake_agent.evals.scenarios import TimeoutDirectory
from support import (
    CONFLICT_EMAIL,
    REQUESTER,
    call,
    good_turns,
    scripted,
    service,
    submit,
    turn,
)

# Module constants
log = get_logger(__name__)


# log.debug("Defines the happy path")
def test_a_good_run_is_submitted_and_audited(settings: AppSettings, store: Store) -> None:
    """Search, draft, request approval: submitted and recorded."""
    # log.debug("Runs the intake")
    result = service(settings, store, scripted(settings, *good_turns(), responder=submit)).run(
        CONFLICT_EMAIL, REQUESTER
    )
    # log.debug("Reads the audit record")
    detail = RunLog(store).detail(result.run.id)
    # log.debug("Checks the outcome, the calls and the steps")
    assert detail is not None and (
        result.run.outcome,
        [c.tool for c in detail.tool_calls],
        len(detail.model_calls),
    ) == (
        "submitted",
        ["search_adverse_parties", "search_clients", "draft_matter", "request_approval"],
        3,
    )


# log.debug("Defines the stop-without-drafting test")
def test_a_model_that_stops_drafts_nothing(settings: AppSettings, store: Store) -> None:
    """Plain words end the run with no draft; they are the reason."""
    # log.debug("Runs with a model that only talks")
    result = service(settings, store, scripted(settings, "Not an intake request.")).run(
        CONFLICT_EMAIL, REQUESTER
    )
    # log.debug("Checks the outcome and reason")
    assert (result.run.outcome, result.run.reason, result.draft) == (
        "no_draft",
        "Not an intake request.",
        None,
    )


# log.debug("Defines the step-limit test")
def test_the_step_limit_ends_a_looping_model(settings: AppSettings, store: Store) -> None:
    """A model that searches forever is stopped at the step limit."""

    # log.debug("Defines a model that always searches")
    def loop(_: list[Any]) -> Any:
        """Search again."""
        # log.debug("Returns another search")
        return turn(call("s", "search_clients", name="Ironwood Builders Inc."))

    # log.debug("Allows three steps")
    limited = settings.model_copy(update={"agent_max_steps": 3})
    # log.debug("Runs the intake")
    result = service(limited, store, scripted(limited, responder=loop)).run(
        CONFLICT_EMAIL, REQUESTER
    )
    # log.debug("Checks it failed at the limit after three model calls")
    assert (result.run.outcome, result.run.reason, result.run.steps) == (
        "failed",
        "the run reached its step limit",
        3,
    )


# log.debug("Defines the tool-call limit test")
def test_the_tool_call_limit(settings: AppSettings, store: Store) -> None:
    """A step that would pass the tool-call limit is not run."""
    # log.debug("Allows two tool calls in all")
    limited = settings.model_copy(update={"agent_max_tool_calls": 2})
    # log.debug("Scripts a step with three searches")
    burst = turn(*(call(f"s{i}", "search_clients", name=f"Party {i}") for i in range(3)))
    # log.debug("Runs the intake")
    result = service(limited, store, scripted(limited, burst)).run(CONFLICT_EMAIL, REQUESTER)
    # log.debug("Checks it failed with no tool call made")
    assert (result.run.outcome, result.run.tool_calls) == ("failed", 0)


# log.debug("Lists the outages to try: the fakes' kind, and a real SDK's after its retries")
OUTAGES = (
    TransientError("down"),
    anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com")),
)


# log.debug("Defines the model-outage test")
@pytest.mark.parametrize("outage", OUTAGES, ids=["fake", "sdk"])
def test_a_model_outage_fails_the_run_cleanly(
    settings: AppSettings, store: Store, outage: Exception
) -> None:
    """An unreachable model ends the run as failed, record closed."""

    # log.debug("Defines a provider that is always down")
    class Down(FakeProvider):
        """Raises the outage on every call."""

        # log.debug("Defines the failing call")
        def complete(self, **_: Any) -> Any:
            """Raise.

            Raises:
                Exception: The outage, always.
            """
            # log.debug("Raises the outage")
            raise outage

    # log.debug("Builds an adapter that never waits between retries")
    adapter = ModelAdapter(Down(), model="fake-model", settings=settings, sleep=lambda _: None)
    # log.debug("Runs the intake")
    result = service(settings, store, adapter).run(CONFLICT_EMAIL, REQUESTER)
    # log.debug("Checks the run closed as failed with a plain reason")
    assert (result.run.outcome, result.run.reason, result.run.finished_at is not None) == (
        "failed",
        "the model could not be reached; try again later",
        True,
    )


# log.debug("Defines the timeout test end to end")
def test_a_database_timeout_ends_incomplete(settings: AppSettings, store: Store) -> None:
    """Searches fail, the draft is refused, and the run says why."""
    # log.debug("Scripts searches, a draft attempt, then words")
    adapter = scripted(settings, *good_turns(), "The check could not be completed.")
    # log.debug("Runs against a database that never answers")
    result = service(settings, store, adapter).run(
        CONFLICT_EMAIL, REQUESTER, directory=TimeoutDirectory()
    )
    # log.debug("Checks the outcome and that nothing was drafted")
    assert (result.run.outcome, result.draft) == ("incomplete", None)


# log.debug("Defines the email length limits")
@pytest.mark.parametrize("email", ["too short", "x" * 20_001])
def test_email_length_limits(settings: AppSettings, store: Store, email: str) -> None:
    """An email outside the limits is refused before any record."""
    # log.debug("Expects the refusal")
    with pytest.raises(ValueError, match="characters"):
        # log.debug("Runs the intake")
        service(settings, store, scripted(settings)).run(email, REQUESTER)
    # log.debug("Checks no run was recorded")
    assert RunLog(store).runs() == []


# log.debug("Defines the test that the email never reaches the audit log")
def test_the_audit_log_holds_the_emails_hash_not_its_text(
    settings: AppSettings, store: Store
) -> None:
    """The run record has the hash and length, never the text."""
    # log.debug("Runs the intake")
    result = service(settings, store, scripted(settings, "Nothing to do.")).run(
        CONFLICT_EMAIL, REQUESTER
    )
    # log.debug("Reads every column of the run")
    record = result.run.model_dump()
    # log.debug("Checks the length is there and the text is not")
    assert record["email_chars"] == len(CONFLICT_EMAIL) and not any(
        "Ironwood" in str(value) for value in record.values()
    )
