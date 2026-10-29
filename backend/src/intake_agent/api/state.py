########################################################################
#                backend/src/intake_agent/api/state.py                 #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           Builds the services the routes share, once, when #
#                     the app starts.                                  #
########################################################################
"""The services the routes share, built once when the app starts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from fastapi import Request
from kds.llm import ModelAdapter
from kds.logs import get_logger

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

# Module constants
log = get_logger(__name__)
# log.debug("Sets the path every route lives under, with its version")
PREFIX = "/api/v1"


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
def build_services(settings: AppSettings, adapter: ModelAdapter | None) -> Services:
    """Open and seed the database and build every service.

    Tests pass an adapter; the service builds one from settings.
    """
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
def build_verifier(settings: AppSettings, keys: KeySource | None) -> EntraVerifier | None:
    """Return the Entra ID checker in entra mode, else None.

    Tests pass a key source; the service fetches the tenant's keys.
    """
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
def services(request: Request) -> Services:
    """Return the services the app built at startup."""
    # log.debug("Returns them from the app's state")
    return cast(Services, request.app.state.services)
