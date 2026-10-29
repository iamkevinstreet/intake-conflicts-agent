########################################################################
#              backend/src/intake_agent/api/approvals.py               #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Serves the routes for drafts: review, decide and open, with each refusal
mapped to its status.

- GET /drafts and /drafts/{id}: approvers see every draft; requesters
  see their own
- POST /drafts/{id}/decision: an approver approves or rejects; not their
  own draft, and a reason is needed to approve past a flag
- POST /drafts/{id}/open: an approver opens the matter; refused (409)
  until an approval record exists
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

from typing import Annotated, Final

# Third-party
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from kds.logs import get_logger

# Local
from intake_agent.api.identity import current_actor, require
from intake_agent.api.schemas import DecisionRequest
from intake_agent.api.state import Services, services
from intake_agent.config import SETTINGS
from intake_agent.core.drafts import (
    DraftNotFoundError,
    DraftStateError,
    GateError,
    ReasonRequiredError,
)
from intake_agent.core.models import Actor, DraftRecord, DraftStatus, NewMatter

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)
# log.debug("Takes the path every route lives under, from the config")
PREFIX: Final = SETTINGS.api_prefix
# log.debug("Takes the shape of a draft id, from the config")
DRAFT_ID: Final = SETTINGS.ids_draft_pattern
# log.debug("Takes the most drafts one list returns, from the config")
MAX_LIST: Final = SETTINGS.api_max_list_limit
# log.debug("Takes the number of drafts a list returns by default, from the config")
DEFAULT_LIST: Final = SETTINGS.api_list_limit
# log.debug("Takes the role these actions need, from the config")
APPROVER: Final = SETTINGS.roles_approver

########################################################################
#                           Local constants                            #
########################################################################
# log.debug("Sets the answer for a draft that does not exist or is not the caller's")
NOT_FOUND = "no such draft"


########################################################################
#                           Approval routes                            #
########################################################################
# log.debug("Creates the router for drafts")
router = APIRouter(prefix=f"{PREFIX}/drafts")


# log.debug("Describes a draft id in a path")
DraftId = Annotated[str, Path(pattern=DRAFT_ID)]


# log.debug("Defines the list of drafts")
@router.get("")
def drafts(
    svc: Annotated[Services, Depends(services)],
    actor: Annotated[Actor, Depends(current_actor)],
    state: Annotated[DraftStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIST)] = DEFAULT_LIST,
) -> list[DraftRecord]:
    """Returns drafts, newest first: everyone's for an approver.

    Args:
        svc: The services the app built at startup.
        actor: The caller; an approver sees every draft, a requester
            only their own.
        state: The status to list, from the status query; None lists
            every status.
        limit: The most drafts to return.

    Returns:
        The drafts the caller may see, newest first.
    """
    # log.debug("Returns the drafts the caller may see")
    return svc.drafts.find(
        status=state,
        requester=None if APPROVER in actor.roles else actor.user_id,
        limit=limit,
    )


# log.debug("Defines one draft")
@router.get("/{draft_id}")
def draft(
    draft_id: DraftId,
    svc: Annotated[Services, Depends(services)],
    actor: Annotated[Actor, Depends(current_actor)],
) -> DraftRecord:
    """Returns a draft with its findings, decision and matter.

    Args:
        draft_id: The draft's id.
        svc: The services the app built at startup.
        actor: The caller, who must be an approver or the draft's
            requester.

    Returns:
        The draft with its status, decision and matter.

    Raises:
        HTTPException: 404 for an unknown draft, or one the caller may
            not see.
    """
    # log.debug("Reads the draft")
    try:
        # log.debug("Fetches it")
        record = svc.drafts.get(draft_id)
    except DraftNotFoundError as error:
        # log.debug("Answers 404")
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from error
    # log.debug("Hides another requester's draft")
    if APPROVER not in actor.roles and record.draft.requester != actor.user_id:
        # log.debug("Answers 404, revealing nothing")
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    # log.debug("Returns it")
    return record


# log.debug("Defines an approver's decision")
@router.post("/{draft_id}/decision")
def decide(
    draft_id: DraftId,
    body: DecisionRequest,
    svc: Annotated[Services, Depends(services)],
    actor: Annotated[Actor, Depends(require(APPROVER))],
) -> DraftRecord:
    """Approves or rejects a pending draft.

    Args:
        draft_id: The draft's id.
        body: The decision and the approver's note.
        svc: The services the app built at startup.
        actor: The caller, who must hold the approver role.

    Returns:
        The draft as it now stands, approved or rejected.

    Raises:
        HTTPException: 404 unknown, 409 not pending, 403 your own draft,
            422 a note over the limit, or approving a flagged draft
            without a reason.
    """
    # log.debug("Refuses a note longer than the setting allows")
    if len(body.note) > svc.settings.api_max_note_chars:
        # log.debug("Answers 422, naming the limit")
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"the note is longer than {svc.settings.api_max_note_chars} characters",
        )
    # log.debug("Records the decision, mapping each refusal to its status")
    try:
        # log.debug("Returns the decided draft")
        return svc.drafts.decide(draft_id, approver=actor, decision=body.decision, note=body.note)
    except DraftNotFoundError as error:
        # log.debug("Answers 404")
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from error
    except DraftStateError as error:
        # log.debug("Answers 409")
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except GateError as error:
        # log.debug("Answers 403")
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(error)) from error
    except ReasonRequiredError as error:
        # log.debug("Answers 422")
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error


# log.debug("Defines opening the matter: the gated action")
@router.post("/{draft_id}/open", status_code=status.HTTP_201_CREATED)
def open_matter(
    draft_id: DraftId,
    svc: Annotated[Services, Depends(services)],
    actor: Annotated[Actor, Depends(require(APPROVER))],
) -> NewMatter:
    """Opens the matter from an approved draft.

    Args:
        draft_id: The approved draft's id.
        svc: The services the app built at startup.
        actor: The caller, who must hold the approver role.

    Returns:
        The new matter, with its number and who opened it.

    Raises:
        HTTPException: 404 unknown, 409 not approved or already open.
    """
    # log.debug("Asks the gate, mapping each refusal to its status")
    try:
        # log.debug("Returns the new matter")
        return svc.drafts.open(draft_id, actor=actor)
    except DraftNotFoundError as error:
        # log.debug("Answers 404")
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from error
    except (GateError, DraftStateError) as error:
        # log.debug("Answers 409: no approval record yet, or already open")
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
