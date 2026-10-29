########################################################################
#                  backend/intake_agent/api/routes.py                  #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           Routes for requesters and everyone signed in:    #
#                     health, me, examples, intake, runs.              #
########################################################################
"""Routes for requesters, and the ones every signed-in person shares.

- GET /health: open, for monitors
- GET /me: who the service thinks you are
- GET /examples: made-up intake emails to try (requesters)
- POST /intake: run the agent on an email (requesters, rate limited)
- GET /runs and /runs/{id}: the audit log; requesters see their own
  runs, approvers see everyone's
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from kds.logs import get_logger

from intake_agent import __version__
from intake_agent.api.identity import current_actor, require
from intake_agent.api.schemas import Example, Health, IntakeRequest, IntakeResponse
from intake_agent.api.state import PREFIX, Services, services
from intake_agent.core.audit import RunDetail, RunRecord
from intake_agent.core.models import RUN_ID, Actor, Role

# Module constants
log = get_logger(__name__)
# log.debug("Creates the router under the API prefix")
router = APIRouter(prefix=PREFIX)
# log.debug("Sets the most runs one list returns")
MAX_LIST = 200
# log.debug("Sets the number of runs a list returns by default")
DEFAULT_LIST = 50
# log.debug("Names the role that sees everyone's records")
APPROVER: Role = "approver"
# log.debug("Names the role that runs intakes")
REQUESTER: Role = "requester"


# log.debug("Defines the health check")
@router.get("/health")
def health(svc: Annotated[Services, Depends(services)]) -> Health:
    """Report the version, sign-in mode, model and database size."""
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
    """Return the caller as the service sees them."""
    # log.debug("Returns the caller")
    return actor


# log.debug("Defines the examples")
@router.get("/examples")
def examples(
    svc: Annotated[Services, Depends(services)],
    _: Annotated[Actor, Depends(require(REQUESTER))],
) -> list[Example]:
    """Return the made-up emails the web app offers to try."""
    # log.debug("Returns them")
    return list(svc.examples)


# log.debug("Defines an intake run")
@router.post("/intake", status_code=status.HTTP_201_CREATED)
def intake(
    body: IntakeRequest,
    svc: Annotated[Services, Depends(services)],
    actor: Annotated[Actor, Depends(require(REQUESTER))],
) -> IntakeResponse:
    """Run the agent on the email, for the caller; return the run.

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
    """Return recent runs: everyone's for an approver, else your own."""
    # log.debug("Returns the runs the caller may see")
    return svc.runlog.runs(requester=_scope(actor), limit=limit)


# log.debug("Defines one run's audit record")
@router.get("/runs/{run_id}")
def run(
    run_id: Annotated[str, Path(pattern=RUN_ID)],
    svc: Annotated[Services, Depends(services)],
    actor: Annotated[Actor, Depends(current_actor)],
) -> RunDetail:
    """Return a run with every model and tool call it made.

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
def _scope(actor: Actor) -> str | None:
    """Return None for an approver (all), else the caller's id."""
    # log.debug("Returns the scope")
    return None if APPROVER in actor.roles else actor.user_id
