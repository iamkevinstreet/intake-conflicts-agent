########################################################################
#                       backend/tests/support.py                       #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           Shared test helpers: people, a seeded store,     #
#                     scripted models and a service with no waits.     #
########################################################################
"""Shared test helpers: the repository root, people, stores, scripts."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from kds.llm import Message, ModelAdapter
from kds.llm.fake import FakeProvider
from kds.logs import get_logger

from intake_agent.config import AppSettings
from intake_agent.core.audit import RunLog
from intake_agent.core.drafts import DraftBook
from intake_agent.core.firm import SqliteDirectory
from intake_agent.core.models import Actor
from intake_agent.core.seed import seed
from intake_agent.core.service import IntakeService
from intake_agent.core.store import Store

# Module constants
log = get_logger(__name__)
# log.debug("Finds the repository root, two folders above this file")
REPO = Path(__file__).resolve().parents[2]
# log.debug("Sets a requester")
REQUESTER = Actor(user_id="dev:avery-stone", name="Avery Stone", roles=frozenset({"requester"}))
# log.debug("Sets an approver")
APPROVER = Actor(user_id="dev:jordan-reyes", name="Jordan Reyes", roles=frozenset({"approver"}))
# log.debug("Sets a second approver")
OTHER_APPROVER = Actor(user_id="dev:sam-ortiz", name="Sam Ortiz", roles=frozenset({"approver"}))
# log.debug("Sets a person who holds both roles")
BOTH = Actor(
    user_id="dev:robin-hale", name="Robin Hale", roles=frozenset({"requester", "approver"})
)
# log.debug("Sets an intake email naming a current client as the other side")
CONFLICT_EMAIL = (
    "We need to sue Ironwood Builders Inc. for unpaid invoices.\n\n"
    "Dana Whitfield\nFalcon Ridge Supply LLC"
)


# log.debug("Defines a seeded store")
def seeded_store(settings: AppSettings) -> Store:
    """Return a migrated, seeded store at the settings' path."""
    # log.debug("Opens the store")
    store = Store(settings.data_database, timeout_s=settings.store_timeout_s)
    # log.debug("Seeds it")
    seed(store, settings)
    # log.debug("Returns it")
    return store


# log.debug("Defines an adapter that plays back scripted turns")
def scripted(
    settings: AppSettings,
    *turns: Any,
    responder: Callable[[list[Message]], Any] | None = None,
) -> ModelAdapter:
    """Return an adapter that plays `turns`, then asks `responder`."""
    # log.debug("Returns it, priced at zero")
    return ModelAdapter(
        FakeProvider(list(turns), responder=responder), model="fake-model", settings=settings
    )


# log.debug("Defines a service around a store and an adapter")
def service(settings: AppSettings, store: Store, adapter: ModelAdapter) -> IntakeService:
    """Return the intake service with no waits between retries."""
    # log.debug("Returns it")
    return IntakeService(
        settings=settings,
        directory=SqliteDirectory(store),
        drafts=DraftBook(store, min_reason_chars=settings.api_min_reason_chars),
        runlog=RunLog(store),
        adapter=adapter,
        sleep=lambda _: None,
    )


# log.debug("Defines one scripted tool call")
def call(call_id: str, tool: str, /, **arguments: Any) -> dict[str, Any]:
    """Return a tool call as the fake provider expects it."""
    # log.debug("Returns it")
    return {"id": call_id, "name": tool, "arguments": arguments}


# log.debug("Defines one scripted turn of tool calls")
def turn(*calls: dict[str, Any]) -> dict[str, Any]:
    """Return a turn that makes the calls."""
    # log.debug("Returns it")
    return {"text": "", "tool_calls": list(calls)}


# log.debug("Defines the draft arguments most tests use")
def draft_args(**changes: Any) -> dict[str, Any]:
    """Return valid draft_matter arguments, with any changes."""
    # log.debug("Returns them")
    return {
        "client": "Falcon Ridge Supply LLC",
        "adverse_parties": ["Ironwood Builders Inc."],
        "matter_type": "collections and non-solicitation",
        "timeline": "before November 12",
        "summary": "A supplier wants to recover unpaid invoices.",
        "recommendation": "conflict",
        "reasoning": "Ironwood Builders Inc. is a current client.",
    } | changes


# log.debug("Defines the turns of a well-behaved run for CONFLICT_EMAIL")
def good_turns() -> list[Any]:
    """Return the searches and the draft; `submit` sends it after."""
    # log.debug("Returns the two turns")
    return [
        turn(
            call("a", "search_adverse_parties", name="Falcon Ridge Supply LLC"),
            call("b", "search_clients", name="Ironwood Builders Inc."),
        ),
        turn(call("c", "draft_matter", **draft_args())),
    ]


# log.debug("Defines a responder that sends the saved draft for approval")
def submit(messages: list[Message]) -> Any:
    """Request approval of the draft just saved; then stop."""
    # log.debug("Reads the last tool result")
    last = json.loads(messages[-1].content) if messages[-1].role == "tool" else {}
    # log.debug("Requests approval right after a draft was saved")
    if "draft_id" in last and "status" not in last:
        # log.debug("Returns the request")
        return turn(call("d", "request_approval", draft_id=last["draft_id"], note="Checked."))
    # log.debug("Stops otherwise")
    return "Done."
