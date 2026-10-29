########################################################################
#                   backend/intake_agent/api/app.py                    #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           Builds the HTTP app: startup, request ids,       #
#                     security headers, hosts, size limits, CORS.      #
########################################################################
"""The FastAPI app factory.

Every response carries the request id and security headers; requests
to a host name not in settings are refused (which stops DNS-rebinding
pages reaching a local server); bodies over the size limit are refused
before they are read; every request is logged as one JSON line; and
errors come back as JSON with the request id and nothing internal.
"""

from __future__ import annotations

import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from kds.llm import ModelAdapter
from kds.logs import get_logger, log_event, new_request_id, setup_logging
from kds.settings import describe

from intake_agent import __version__
from intake_agent.api import approvals, routes
from intake_agent.api.identity import KeySource
from intake_agent.api.state import PREFIX, build_services, build_verifier
from intake_agent.config import AppSettings, get_app_settings

# Module constants
log = get_logger(__name__)
# log.debug("Names the header that carries the request id")
REQUEST_ID = "X-Request-ID"
# log.debug("Matches a request id a client may supply")
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# log.debug("Sets the headers every response carries")
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Cross-Origin-Resource-Policy": "same-origin",
}
# log.debug("Sets the bytes one character of an email may take in UTF-8, at most")
BYTES_PER_CHAR = 4
# log.debug("Sets the room for JSON around the email")
BODY_SLACK_BYTES = 4096
# log.debug("Sets the milliseconds in a second")
MS = 1000
# log.debug("Describes the next step in the middleware chain")
Next = Callable[[Request], Awaitable[Response]]


# log.debug("Defines the app factory")
def create_app(
    settings: AppSettings | None = None,
    *,
    adapter: ModelAdapter | None = None,
    keys: KeySource | None = None,
) -> FastAPI:
    """Build the app; tests pass settings, an adapter and keys."""
    # log.debug("Uses the given settings or the configured ones")
    config = settings or get_app_settings()

    # log.debug("Defines startup: logging, the settings record, the services")
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Set up logging, log every setting (secrets masked), build."""
        # log.debug("Sets up JSON logging")
        setup_logging(config)
        # log.debug("Logs the version and every setting, secrets masked")
        log_event(log, "service.start", version=__version__, settings=describe(config))
        # log.debug("Builds the database, drafts, audit log and agent")
        app.state.services = build_services(config, adapter)
        # log.debug("Serves requests until shutdown")
        yield

    # log.debug("Creates the app, with its schema under the API prefix")
    app = FastAPI(
        title="New-matter intake agent",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=f"{PREFIX}/openapi.json",
    )
    # log.debug("Keeps the settings for the sign-in check")
    app.state.settings = config
    # log.debug("Builds the Entra ID token check, in entra mode")
    app.state.verifier = build_verifier(config, keys)
    # log.debug("Allows only the configured browser origins")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.api_allowed_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Dev-User", "X-Dev-Role", REQUEST_ID],
        expose_headers=[REQUEST_ID],
    )
    # log.debug("Adds the request id, size limit, headers and request log")
    app.middleware("http")(_edge(config.agent_max_email_chars * BYTES_PER_CHAR + BODY_SLACK_BYTES))
    # log.debug("Refuses requests addressed to any other host name")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(config.api_allowed_hosts))
    # log.debug("Adds the requester routes")
    app.include_router(routes.router)
    # log.debug("Adds the draft and approval routes")
    app.include_router(approvals.router)
    # log.debug("Returns the app")
    return app


# log.debug("Defines the middleware every request passes through")
def _edge(max_body: int) -> Callable[[Request, Next], Awaitable[Response]]:
    """Return middleware that ids, limits, logs and secures."""

    # log.debug("Defines the middleware itself")
    async def edge(request: Request, call_next: Next) -> Response:
        """Run the request under its id; refuse oversized bodies."""
        # log.debug("Takes the client's request id only if it is well formed")
        given = request.headers.get(REQUEST_ID, "")
        # log.debug("Starts the clock")
        started = time.perf_counter()
        # log.debug("Runs the request under its id")
        with new_request_id(given if REQUEST_ID_RE.fullmatch(given) else None) as request_id:
            # log.debug("Reads the declared body size")
            length = request.headers.get("content-length", "0")
            # log.debug("Refuses a body over the limit before reading it")
            if not length.isdigit() or int(length) > max_body:
                # log.debug("Answers 413")
                response: Response = JSONResponse(
                    {"detail": "request body too large"}, status.HTTP_413_CONTENT_TOO_LARGE
                )
            else:
                # log.debug("Passes the request on")
                response = await call_next(request)
            # log.debug("Adds the security headers and the request id")
            response.headers.update({**SECURITY_HEADERS, REQUEST_ID: request_id})
            # log.debug("Logs the request as one JSON line")
            log_event(
                log,
                "http.request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                ms=int((time.perf_counter() - started) * MS),
            )
        # log.debug("Returns the response")
        return response

    # log.debug("Returns the middleware")
    return edge
