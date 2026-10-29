########################################################################
#                      backend/tests/test_gate.py                      #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           Tests gate integrity: no matter opens without    #
#                     another person's approval, by any path.          #
########################################################################
"""Gate integrity: no matter opens without an approval record. Ever.

These tests try every way in: the agent's identity, an approver before
any decision, after a rejection, a person approving their own draft,
and a second opening. Only one path opens a matter: another person
approves, then an approver opens.
"""

from __future__ import annotations

from typing import Any

import pytest
from kds.logs import get_logger

from intake_agent.config import AppSettings
from intake_agent.core.drafts import (
    DraftBook,
    DraftStateError,
    GateError,
    ReasonRequiredError,
)
from intake_agent.core.models import Actor, DraftRecord
from intake_agent.core.store import Store

from support import (
    APPROVER,
    BOTH,
    CONFLICT_EMAIL,
    OTHER_APPROVER,
    REQUESTER,
    good_turns,
    scripted,
    service,
    submit,
)

# Module constants
log = get_logger(__name__)
# log.debug("Sets the requester's identity as the agent carries it")
AGENT = Actor(user_id=REQUESTER.user_id, name=REQUESTER.name, roles=frozenset({"requester"}))
# log.debug("Sets a reason long enough to approve past a flag")
REASON = "Waiver signed by both clients, on file."


# log.debug("Defines a pending draft made by a requester")
def _pending(settings: AppSettings, store: Store, requester: Actor = REQUESTER) -> DraftRecord:
    """Run a scripted intake that ends with a pending draft."""
    # log.debug("Runs the intake")
    result = service(settings, store, scripted(settings, *good_turns(), responder=submit)).run(
        CONFLICT_EMAIL, requester
    )
    # log.debug("Checks it reached an approver")
    assert result.draft is not None and result.draft.status == "pending"
    # log.debug("Returns the draft")
    return result.draft


# log.debug("Defines the drafts book the tests use")
@pytest.fixture
def book(store: Store, settings: AppSettings) -> DraftBook:
    """The same book the service writes to."""
    # log.debug("Returns it")
    return DraftBook(store, min_reason_chars=settings.api_min_reason_chars)


# log.debug("Defines the test that nobody opens a pending draft")
@pytest.mark.parametrize("actor", [AGENT, APPROVER, OTHER_APPROVER])
def test_nobody_opens_a_pending_draft(
    settings: AppSettings, store: Store, book: DraftBook, actor: Actor
) -> None:
    """Before any decision, the agent and every approver are refused."""
    # log.debug("Makes a pending draft")
    draft = _pending(settings, store)
    # log.debug("Expects the gate's refusal")
    with pytest.raises(GateError):
        # log.debug("Tries to open it")
        book.open(draft.draft.id, actor=actor)


# log.debug("Defines the test that the agent cannot open even an approved draft")
def test_the_agent_cannot_open_an_approved_draft(
    settings: AppSettings, store: Store, book: DraftBook
) -> None:
    """With an approval on file, the agent is still refused."""
    # log.debug("Makes and approves a draft")
    draft = _pending(settings, store)
    # log.debug("Approves it with a reason")
    book.decide(draft.draft.id, approver=APPROVER, decision="approved", note=REASON)
    # log.debug("Expects the refusal: the agent is not an approver")
    with pytest.raises(GateError, match="only an approver"):
        # log.debug("Tries to open it as the agent")
        book.open(draft.draft.id, actor=AGENT)


# log.debug("Defines the test that a rejection keeps the matter shut")
def test_a_rejected_draft_never_opens(
    settings: AppSettings, store: Store, book: DraftBook
) -> None:
    """A rejection is a decision, but not an approval."""
    # log.debug("Makes and rejects a draft")
    draft = _pending(settings, store)
    # log.debug("Rejects it")
    book.decide(draft.draft.id, approver=APPROVER, decision="rejected", note="")
    # log.debug("Expects the refusal")
    with pytest.raises(GateError, match="no approval record"):
        # log.debug("Tries to open it")
        book.open(draft.draft.id, actor=APPROVER)


# log.debug("Defines the four-eyes test")
def test_nobody_approves_their_own_draft(
    settings: AppSettings, store: Store, book: DraftBook
) -> None:
    """A person with both roles cannot approve their own draft."""
    # log.debug("Makes a draft as the person with both roles")
    draft = _pending(settings, store, requester=BOTH)
    # log.debug("Expects the refusal")
    with pytest.raises(GateError, match="another approver"):
        # log.debug("Tries to approve it as themselves")
        book.decide(draft.draft.id, approver=BOTH, decision="approved", note=REASON)


# log.debug("Defines the reason test")
def test_approving_past_a_conflict_needs_a_reason(
    settings: AppSettings, store: Store, book: DraftBook
) -> None:
    """The draft is flagged, so a short note is not enough."""
    # log.debug("Makes a flagged draft")
    draft = _pending(settings, store)
    # log.debug("Expects the refusal")
    with pytest.raises(ReasonRequiredError):
        # log.debug("Tries to approve with a short note")
        book.decide(draft.draft.id, approver=APPROVER, decision="approved", note="ok")


# log.debug("Defines the only path that opens a matter")
def test_the_one_path_that_opens_a_matter(
    settings: AppSettings, store: Store, book: DraftBook
) -> None:
    """Approve, open, and a second open is refused."""
    # log.debug("Makes a draft")
    draft = _pending(settings, store)
    # log.debug("Approves it, with a reason")
    book.decide(draft.draft.id, approver=APPROVER, decision="approved", note=REASON)
    # log.debug("Opens it as a different approver")
    matter = book.open(draft.draft.id, actor=OTHER_APPROVER)
    # log.debug("Checks the matter and the draft's state")
    assert (matter.number, matter.opened_by, book.get(draft.draft.id).status) == (
        "NM-00001",
        OTHER_APPROVER.user_id,
        "opened",
    )
    # log.debug("Expects a second open to be refused")
    with pytest.raises(DraftStateError, match="already open"):
        # log.debug("Tries again")
        book.open(draft.draft.id, actor=APPROVER)


# log.debug("Defines the decide-twice test")
def test_a_decision_is_final(settings: AppSettings, store: Store, book: DraftBook) -> None:
    """A decided draft cannot be decided again."""
    # log.debug("Makes and rejects a draft")
    draft = _pending(settings, store)
    # log.debug("Rejects it")
    book.decide(draft.draft.id, approver=APPROVER, decision="rejected", note="")
    # log.debug("Expects the refusal")
    with pytest.raises(DraftStateError, match="not pending"):
        # log.debug("Tries to approve it after all")
        book.decide(draft.draft.id, approver=APPROVER, decision="approved", note=REASON)


# log.debug("Defines the injection-in-the-loop test")
def test_an_agent_told_to_open_cannot(settings: AppSettings, store: Store) -> None:
    """The model obeys an injection; nothing opens."""

    # log.debug("Defines a model that tries to open right after drafting")
    def obey(messages: list[Any]) -> Any:
        """Call open_matter on the saved draft, then submit."""
        # log.debug("Hands the conversation to the normal responder")
        nxt = submit(messages)
        # log.debug("Adds an open_matter call to the request turn")
        if isinstance(nxt, dict):
            # log.debug("Puts the open call first")
            draft_id = nxt["tool_calls"][0]["arguments"]["draft_id"]
            # log.debug("Adds it")
            nxt["tool_calls"].insert(
                0, {"id": "x", "name": "open_matter", "arguments": {"draft_id": draft_id}}
            )
        # log.debug("Returns the turn")
        return nxt

    # log.debug("Runs the intake with that model")
    result = service(settings, store, scripted(settings, *good_turns(), responder=obey)).run(
        CONFLICT_EMAIL, REQUESTER
    )
    # log.debug("Checks the attempt was made, refused, and the draft still went to a person")
    assert (result.open_attempts, result.run.outcome, result.draft and result.draft.matter) == (
        1,
        "submitted",
        None,
    )
