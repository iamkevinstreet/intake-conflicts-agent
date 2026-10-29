########################################################################
#                backend/src/intake_agent/api/state.py                 #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Builds the services the routes share, once, when the app starts, and the
Entra ID token check when sign-in needs one. Routes reach the services
through the `services` dependency.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

from dataclasses import dataclass
from typing import cast

# Third-party
from fastapi import Request
from kds.args import required
from kds.llm import ModelAdapter
from kds.logs import get_logger

# Local
from intake_agent.api.identity import EntraKeys, EntraVerifier, KeySource
from intake_agent.api.limits import RateLimiter
from intake_agent.api.schemas import Example
from intake_agent.config import AppSettings
from intake_agent.core.audit import RunLog
from intake_agent.core.drafts import DraftBook
from intake_agent.core.firm import SqliteDirectory
from intake_agent.core.offline import adapter_for
from intake_agent.core.seed import seed
from intake_agent.core.service import IntakeService
from intake_agent.core.store import Store
from intake_agent.evals.scenarios import load_scenarios

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)


########################################################################
#                             App services                             #
########################################################################
# log.debug("Defines the services the routes share")
@dataclass(frozen=True)
class Services:
    """Everything a route needs, built once per app."""

    # log.debug("Holds the settings")
    settings: AppSettings
    # log.debug("Holds the firm's records, read only")
    directory: SqliteDirectory
    # log.debug("Holds the drafts")
    drafts: DraftBook
    # log.debug("Holds the audit log")
    runlog: RunLog
    # log.debug("Holds the intake service")
    intake: IntakeService
    # log.debug("Holds the per-person limit on intakes")
    limiter: RateLimiter
    # log.debug("Holds the examples the web app offers")
    examples: tuple[Example, ...]


# log.debug("Defines how the services are built at startup")
def build_services(
    settings: AppSettings | None = None, adapter: ModelAdapter | None = None
) -> Services:
    """Opens and seeds the database and builds every service.

    Tests pass an adapter; the service builds one from settings.

    Args:
        settings: The app's settings. Required.
        adapter: The model adapter; None builds the one the settings
            name.

    Returns:
        Every service the routes share, built on one database.
    """
    # log.debug("Takes the settings, which the caller must give")
    settings = required(settings=settings)
    # log.debug("Opens the database, migrating it")
    store = Store(settings.data_database, timeout_s=settings.store_timeout_s)
    # log.debug("Seeds it the first time")
    seed(store, settings)
    # log.debug("Builds the read-only view of the firm")
    directory = SqliteDirectory(store)
    # log.debug("Builds the drafts book")
    drafts = DraftBook(store, min_reason_chars=settings.api_min_reason_chars)
    # log.debug("Builds the audit log")
    runlog = RunLog(store)
    # log.debug("Reads the examples named in settings")
    examples = tuple(
        Example(id=s.id, title=s.title, email=s.email)
        for s in load_scenarios(settings.data_scenarios)
        if s.id in settings.ui_examples
    )
    # log.debug("Returns the services")
    return Services(
        settings=settings,
        directory=directory,
        drafts=drafts,
        runlog=runlog,
        intake=IntakeService(
            settings=settings,
            directory=directory,
            drafts=drafts,
            runlog=runlog,
            adapter=adapter or adapter_for(settings),
        ),
        limiter=RateLimiter(settings.api_intakes_per_minute),
        examples=examples,
    )


# log.debug("Defines the token checker the settings call for")
def build_verifier(
    settings: AppSettings | None = None, keys: KeySource | None = None
) -> EntraVerifier | None:
    """Returns the Entra ID checker in entra mode, else None.

    Tests pass a key source; the service fetches the tenant's keys.

    Args:
        settings: The app's settings. Required.
        keys: Where signing keys come from; None fetches the tenant's
            published keys.

    Returns:
        The token check in entra mode, or None in dev mode.
    """
    # log.debug("Takes the settings, which the caller must give")
    settings = required(settings=settings)
    # log.debug("Returns no checker in dev mode")
    if settings.auth_mode != "entra":
        # log.debug("Returns None")
        return None
    # log.debug("Returns the checker with the given or the tenant's keys")
    return EntraVerifier(
        settings,
        keys or EntraKeys(settings.entra_tenant_id, cache_s=settings.entra_keys_cache_s),
    )


# log.debug("Defines the dependency routes declare to get the services")
def services(request: Request) -> Services:  # fixed: FastAPI's dependency signature
    """Returns the services the app built at startup.

    Args:
        request: The request FastAPI is answering; its app holds the
            services.

    Returns:
        The services the app built when it started.
    """
    # log.debug("Returns them from the app's state")
    return cast(Services, request.app.state.services)
