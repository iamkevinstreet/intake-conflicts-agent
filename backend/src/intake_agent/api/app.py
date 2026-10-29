########################################################################
#                 backend/src/intake_agent/api/app.py                  #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Builds the HTTP app: startup, request ids, security headers, hosts, size
limits and CORS. Every response carries the request id and security
headers; requests to a host name not in settings are refused (which
stops DNS-rebinding pages reaching a local server); bodies over the size
limit are refused before they are read; every request is logged as one
JSON line; and errors come back as JSON with the request id and nothing
internal.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

import logging
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Final

# Third-party
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from kds.args import required
from kds.llm import ModelAdapter
from kds.logs import get_logger, log_event, new_request_id, setup_logging
from kds.settings import describe

# Local
from intake_agent import __version__
from intake_agent.api import approvals, routes
from intake_agent.api.identity import KeySource
from intake_agent.api.state import build_services, build_verifier
from intake_agent.config import SETTINGS, AppSettings, get_app_settings

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)
# log.debug("Takes the path every route lives under, from the config")
PREFIX: Final = SETTINGS.api_prefix
# log.debug("Takes the header that carries the request id, from the config")
REQUEST_ID: Final = SETTINGS.api_request_id_header
# log.debug("Takes the milliseconds in a second, from the config")
MS: Final = SETTINGS.units_ms_per_second

########################################################################
#                           Local constants                            #
########################################################################
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
# log.debug("Lists the methods that carry a body, which must declare its length")
BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})
# log.debug("Names the header that declares a body's length")
CONTENT_LENGTH = "content-length"
# log.debug("Names the field an error reply explains itself in")
DETAIL = "detail"
# log.debug("Describes the next step in the middleware chain")
Next = Callable[[Request], Awaitable[Response]]


########################################################################
#                               HTTP app                               #
########################################################################
# log.debug("Defines the app factory")
def create_app(
    settings: AppSettings | None = None,
    *,
    adapter: ModelAdapter | None = None,
    keys: KeySource | None = None,
) -> FastAPI:
    """Builds the app; tests pass settings, an adapter and keys.

    Args:
        settings: The app's settings; None reads the configured ones.
        adapter: The model adapter; None builds the one the settings
            name.
        keys: Where Entra ID signing keys come from; None fetches the
            tenant's published keys.

    Returns:
        The app, with its routes, middleware and startup.
    """
    # log.debug("Uses the given settings or the configured ones")
    config = settings or get_app_settings()

    # log.debug("Defines startup: logging, the settings record, the services")
    @asynccontextmanager
    async def lifespan(app: FastAPI | None = None) -> AsyncIterator[None]:
        """Sets up logging, logs every setting and builds the services.

        Args:
            app: The app that is starting, which keeps the services.
                Required.

        Yields:
            Nothing: the app serves requests until the context ends.
        """
        # log.debug("Takes the app that is starting, which the caller must give")
        app = required(app=app)
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
    # log.debug("Refuses requests for any other host name; added first, so it sits innermost")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(config.api_allowed_hosts))
    # log.debug("Allows only the configured browser origins")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.api_allowed_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Dev-User", "X-Dev-Role", REQUEST_ID],
        expose_headers=[REQUEST_ID],
    )
    # log.debug("Adds the request id, limits, headers and log, outermost, so every reply has them")
    app.middleware("http")(_edge(config.agent_max_email_chars * BYTES_PER_CHAR + BODY_SLACK_BYTES))
    # log.debug("Adds the requester routes")
    app.include_router(routes.router)
    # log.debug("Adds the draft and approval routes")
    app.include_router(approvals.router)
    # log.debug("Returns the app")
    return app


# log.debug("Defines the middleware every request passes through")
def _edge(max_body: int | None = None) -> Callable[[Request, Next], Awaitable[Response]]:
    """Returns middleware that ids, limits, logs and secures.

    Args:
        max_body: The largest body accepted, in bytes. Required.

    Returns:
        The middleware, which FastAPI calls with each request and the
        next step in the chain.
    """
    # log.debug("Takes the largest body allowed, which the caller must give")
    max_body = required(max_body=max_body)

    # log.debug("Defines the middleware itself")
    async def edge(request: Request, call_next: Next) -> Response:  # fixed: Starlette's signature
        """Runs the request under its id, refusing oversized bodies.

        Args:
            request: The request to answer.
            call_next: The next step in the middleware chain, which
                answers the request.

        Returns:
            The response, with the security headers and the request id.
        """
        # log.debug("Takes the client's request id only if it is well formed")
        given = request.headers.get(REQUEST_ID, "")
        # log.debug("Starts the clock")
        started = time.perf_counter()
        # log.debug("Runs the request under its id")
        with new_request_id(given if REQUEST_ID_RE.fullmatch(given) else None) as request_id:
            # log.debug("Answers the request, or refuses its body before reading it")
            response = await _answer(request, call_next, max_body)
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


# log.debug("Defines the body checks and the call to the app")
async def _answer(
    request: Request | None = None, call_next: Next | None = None, max_body: int | None = None
) -> Response:
    """Refuses a body with no declared length or one over the limit.

    A chunked body declares no length, so it could only be measured by
    reading it; it is refused instead. An error nobody planned for
    becomes a plain 500 here, so it still carries the headers.

    Args:
        request: The request to answer. Required.
        call_next: The next step in the middleware chain. Required.
        max_body: The largest body accepted, in bytes. Required.

    Returns:
        The app's response, or a 411, 413 or 500 answer.
    """
    # log.debug("Takes the request, which the caller must give")
    request = required(request=request)
    # log.debug("Takes the next step in the chain, which the caller must give")
    call_next = required(call_next=call_next)
    # log.debug("Takes the largest body allowed, which the caller must give")
    max_body = required(max_body=max_body)
    # log.debug("Reads the declared body size")
    length = request.headers.get(CONTENT_LENGTH)
    # log.debug("Refuses a body that does not declare its length")
    if length is None and request.method in BODY_METHODS:
        # log.debug("Answers 411")
        return JSONResponse(
            {DETAIL: "send the body with a Content-Length"}, status.HTTP_411_LENGTH_REQUIRED
        )
    # log.debug("Refuses a body over the limit")
    if length is not None and (not length.isdigit() or int(length) > max_body):
        # log.debug("Answers 413")
        return JSONResponse({DETAIL: "request body too large"}, status.HTTP_413_CONTENT_TOO_LARGE)
    # log.debug("Passes the request on")
    try:
        # log.debug("Returns the app's response")
        return await call_next(request)
    except Exception as error:  # noqa: BLE001 - an unplanned error still gets a reply with headers
        # log.debug("Logs the error's type, never its message")
        log_event(log, "http.error", logging.ERROR, error=type(error).__name__)
        # log.debug("Answers 500")
        return JSONResponse({DETAIL: "internal error"}, status.HTTP_500_INTERNAL_SERVER_ERROR)
