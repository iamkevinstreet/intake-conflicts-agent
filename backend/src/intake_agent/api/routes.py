########################################################################
#                backend/src/intake_agent/api/routes.py                #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Serves the routes for requesters and for everyone signed in:

- GET /health: open, for monitors
- GET /me: who the service thinks you are
- GET /examples: made-up intake emails to try (requesters)
- POST /intake: run the agent on an email (requesters, rate limited)
- GET /runs and /runs/{id}: the audit log; requesters see their own
  runs, approvers see everyone's
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

from typing import Annotated, Final

# Third-party
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from kds.args import required
from kds.logs import get_logger

# Local
from intake_agent import __version__
from intake_agent.api.identity import current_actor, require
from intake_agent.api.schemas import Example, Health, IntakeRequest, IntakeResponse
from intake_agent.api.state import Services, services
from intake_agent.config import SETTINGS
from intake_agent.core.models import Actor
from intake_agent.core.records import RunDetail, RunRecord

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)
# log.debug("Takes the path every route lives under, from the config")
PREFIX: Final = SETTINGS.api_prefix
# log.debug("Takes the shape of a run id, from the config")
RUN_ID: Final = SETTINGS.ids_run_pattern
# log.debug("Takes the most runs one list returns, from the config")
MAX_LIST: Final = SETTINGS.api_max_list_limit
# log.debug("Takes the number of runs a list returns by default, from the config")
DEFAULT_LIST: Final = SETTINGS.api_list_limit
# log.debug("Takes the role that sees everyone's records, from the config")
APPROVER: Final = SETTINGS.roles_approver
# log.debug("Takes the role that runs intakes, from the config")
REQUESTER: Final = SETTINGS.roles_requester


########################################################################
#                           Requester routes                           #
########################################################################
# log.debug("Creates the router under the API prefix")
router = APIRouter(prefix=PREFIX)


# log.debug("Defines the health check")
@router.get("/health")
def health(svc: Annotated[Services, Depends(services)]) -> Health:
    """Reports the version, sign-in mode, model and database size.

    Args:
        svc: The services the app built at startup.

    Returns:
        The status, version, sign-in mode, provider, model and the
        firm's record counts.
    """
    # log.debug("Returns the report")
    return Health(
        status="ok",
        version=__version__,
        auth_mode=svc.settings.auth_mode,
        provider=svc.settings.llm_provider,
        model=svc.intake.adapter.model,
        firm=svc.directory.counts(),
    )


# log.debug("Defines who-am-I")
@router.get("/me")
def me(actor: Annotated[Actor, Depends(current_actor)]) -> Actor:
    """Returns the caller as the service sees them.

    Args:
        actor: The caller, as the sign-in check identified them.

    Returns:
        The caller's id, name and roles.
    """
    # log.debug("Returns the caller")
    return actor


# log.debug("Defines the examples")
@router.get("/examples")
def examples(
    svc: Annotated[Services, Depends(services)],
    _: Annotated[Actor, Depends(require(REQUESTER))],
) -> list[Example]:
    """Returns the made-up emails the web app offers to try.

    Args:
        svc: The services the app built at startup.
        _: The caller, who must hold the requester role.

    Returns:
        The example emails the settings name.
    """
    # log.debug("Returns them")
    return list(svc.examples)


# log.debug("Defines an intake run")
@router.post("/intake", status_code=status.HTTP_201_CREATED)
def intake(
    body: IntakeRequest,
    svc: Annotated[Services, Depends(services)],
    actor: Annotated[Actor, Depends(require(REQUESTER))],
) -> IntakeResponse:
    """Runs the agent on the email for the caller; returns the run.

    Args:
        body: The pasted intake email.
        svc: The services the app built at startup.
        actor: The caller, who must hold the requester role.

    Returns:
        The run's record, its draft if one was saved, and the agent's
        last words.

    Raises:
        HTTPException: 429 past the per-minute limit, 422 for an email
            outside the length limits.
    """
    # log.debug("Refuses a caller past their per-minute limit")
    if not svc.limiter.allow(actor.user_id):
        # log.debug("Refuses with 429 and a retry hint")
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "too many intakes this minute; try again shortly",
            {"Retry-After": "60"},
        )
    # log.debug("Runs the intake")
    try:
        # log.debug("Runs it for the caller")
        result = svc.intake.run(body.email, actor)
    except ValueError as error:
        # log.debug("Refuses an email outside the limits with the reason")
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
    # log.debug("Returns the run, its draft and the agent's last words")
    return IntakeResponse(run=result.run, draft=result.draft, text=result.text)


# log.debug("Defines the list of runs")
@router.get("/runs")
def runs(
    svc: Annotated[Services, Depends(services)],
    actor: Annotated[Actor, Depends(current_actor)],
    limit: Annotated[int, Query(ge=1, le=MAX_LIST)] = DEFAULT_LIST,
) -> list[RunRecord]:
    """Returns recent runs: everyone's for an approver, else your own.

    Args:
        svc: The services the app built at startup.
        actor: The caller; an approver sees everyone's runs.
        limit: The most runs to return.

    Returns:
        The runs the caller may see, newest first.
    """
    # log.debug("Returns the runs the caller may see")
    return svc.runlog.runs(requester=_scope(actor), limit=limit)


# log.debug("Defines one run's audit record")
@router.get("/runs/{run_id}")
def run(
    run_id: Annotated[str, Path(pattern=RUN_ID)],
    svc: Annotated[Services, Depends(services)],
    actor: Annotated[Actor, Depends(current_actor)],
) -> RunDetail:
    """Returns a run with every model and tool call it made.

    Args:
        run_id: The run's id.
        svc: The services the app built at startup.
        actor: The caller, who must be an approver or the run's
            requester.

    Returns:
        The run with its model calls and tool calls, in order.

    Raises:
        HTTPException: 404 for an unknown run, or one the caller may not
            see (so its existence is not revealed).
    """
    # log.debug("Reads the run")
    detail = svc.runlog.detail(run_id)
    # log.debug("Hides runs that do not exist or are not the caller's")
    if detail is None or _scope(actor) not in (None, detail.run.requester):
        # log.debug("Answers 404")
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such run")
    # log.debug("Returns it")
    return detail


# log.debug("Defines whose records a caller may see")
def _scope(actor: Actor | None = None) -> str | None:
    """Returns None for an approver (all), else the caller's id.

    Args:
        actor: The caller. Required.

    Returns:
        None for an approver, who may see everyone's records, else the
        caller's own id.
    """
    # log.debug("Takes the actor, which the caller must give")
    actor = required(actor=actor)
    # log.debug("Returns the scope")
    return None if APPROVER in actor.roles else actor.user_id
