########################################################################
#               backend/src/intake_agent/api/identity.py               #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           Who is calling: Entra ID tokens checked against  #
#                     the tenant's keys, or dev headers locally.       #
########################################################################
"""Who is calling, and which roles they hold.

Two modes, set by [auth] mode:

- "entra": a Microsoft Entra ID access token in the Authorization
  header. The signature is checked against the tenant's published keys
  (RS256 only), and the issuer, audience, expiry and tenant must match.
  Roles come from the token's `roles` claim, mapped from the app roles
  named in settings. The user is the token's object id (`oid`).
- "dev": the X-Dev-User and X-Dev-Role headers are trusted as given.
  Settings refuse this mode on any address but this machine's, so it
  can only ever serve a developer at their own keyboard.

A failure is logged with its reason and never with the token.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Annotated, Any, Protocol

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from kds.logs import get_logger, log_event

from intake_agent.config import AppSettings
from intake_agent.core.models import Actor, Role

# Module constants
log = get_logger(__name__)
# log.debug("Sets the scheme a token header must use")
SCHEME = "Bearer "
# log.debug("Sets the header that tells a client how to sign in")
CHALLENGE = {"WWW-Authenticate": "Bearer"}
# log.debug("Sets the only signing algorithm accepted; never none, never HMAC")
ALGORITHMS = ["RS256"]
# log.debug("Names the claim that holds the user's object id")
OID = "oid"
# log.debug("Lists the claims a token must carry")
REQUIRED = ["exp", "iat", "iss", "aud", OID, "tid"]
# log.debug("Sets Entra ID's sign-in host")
LOGIN = "https://login.microsoftonline.com"
# log.debug("Matches a dev user name: a letter, then letters, spaces, dots, quotes, hyphens")
DEV_USER_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{0,59}$")
# log.debug("Lists the roles a dev header may name")
DEV_ROLES: dict[str, Role] = {"requester": "requester", "approver": "approver"}
# log.debug("Names the event a refused sign-in logs")
DENIED = "auth.denied"


# log.debug("Defines where signing keys come from")
class KeySource(Protocol):
    """Finds the public key a token was signed with."""

    # log.debug("Defines the lookup")
    def key_for(self, token: str) -> Any:
        """Return the public key for the token's key id."""


# log.debug("Defines the tenant's published keys, fetched and cached")
class EntraKeys:
    """The tenant's signing keys, from its JWKS endpoint, cached."""

    # log.debug("Defines the constructor")
    def __init__(self, tenant_id: str, *, cache_s: int) -> None:
        """Read `tenant_id` keys, cached for `cache_s` seconds."""
        # log.debug("Builds the key client for the tenant's endpoint")
        self._client = jwt.PyJWKClient(
            f"{LOGIN}/{tenant_id}/discovery/v2.0/keys", cache_keys=True, lifespan=cache_s
        )

    # log.debug("Defines the lookup")
    def key_for(self, token: str) -> Any:
        """Return the key the token names, fetching keys if needed."""
        # log.debug("Returns the key")
        return self._client.get_signing_key_from_jwt(token).key


# log.debug("Defines the token check")
class EntraVerifier:
    """Turns an Entra ID access token into an actor, or refuses it."""

    # log.debug("Defines the constructor")
    def __init__(self, settings: AppSettings, keys: KeySource) -> None:
        """Check tokens against `settings`, with keys from `keys`."""
        # log.debug("Keeps the settings")
        self.settings = settings
        # log.debug("Keeps the key source")
        self.keys = keys
        # log.debug("Maps the tenant's app roles to ours")
        self.roles: dict[str, Role] = {
            settings.entra_requester_role: "requester",
            settings.entra_approver_role: "approver",
        }

    # log.debug("Defines the check")
    def actor(self, token: str) -> Actor:
        """Return who the token says is calling, with their roles.

        Raises:
            HTTPException: 401 for a token that fails any check, 403
                for a valid token with none of our roles.
        """
        # log.debug("Checks the signature and every required claim")
        try:
            # log.debug("Decodes and verifies the token")
            claims = jwt.decode(
                token,
                self.keys.key_for(token),
                algorithms=ALGORITHMS,
                audience=self.settings.entra_audience,
                issuer=f"{LOGIN}/{self.settings.entra_tenant_id}/v2.0",
                leeway=self.settings.entra_leeway_s,
                options={"require": REQUIRED},
            )
        except jwt.PyJWTError as error:
            # log.debug("Refuses it, logging only the kind of failure")
            raise _refuse(status.HTTP_401_UNAUTHORIZED, type(error).__name__) from error
        # log.debug("Refuses a token from another tenant")
        if claims["tid"] != self.settings.entra_tenant_id:
            # log.debug("Refuses it")
            raise _refuse(status.HTTP_401_UNAUTHORIZED, "tenant")
        # log.debug("Maps the token's app roles to ours")
        roles = frozenset(self.roles[r] for r in claims.get("roles", []) if r in self.roles)
        # log.debug("Refuses a signed-in user with none of our roles")
        if not roles:
            # log.debug("Refuses with 403")
            raise _refuse(status.HTTP_403_FORBIDDEN, "no role")
        # log.debug("Returns the actor, named for display")
        return Actor(
            user_id=str(claims[OID]),
            name=str(claims.get("name") or claims.get("preferred_username") or claims[OID]),
            roles=roles,
        )


# log.debug("Defines the dependency every protected route uses")
def current_actor(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_dev_user: Annotated[str | None, Header()] = None,
    x_dev_role: Annotated[str | None, Header()] = None,
) -> Actor:
    """Return the caller, by the configured mode.

    Raises:
        HTTPException: 401 when the caller cannot be identified, 403
            when they hold no role.
    """
    # log.debug("Reads the settings the app was built with")
    settings: AppSettings = request.app.state.settings
    # log.debug("Uses the dev headers in dev mode")
    if settings.auth_mode == "dev":
        # log.debug("Returns the dev actor")
        return _dev_actor(x_dev_user, x_dev_role)
    # log.debug("Refuses a request without a bearer token")
    if authorization is None or not authorization.startswith(SCHEME):
        # log.debug("Refuses it")
        raise _refuse(status.HTTP_401_UNAUTHORIZED, "no token")
    # log.debug("Checks the token")
    verifier: EntraVerifier = request.app.state.verifier
    # log.debug("Returns the actor the token names")
    return verifier.actor(authorization[len(SCHEME) :])


# log.debug("Defines the dependency for a route that needs one role")
def require(role: Role) -> Callable[..., Actor]:
    """Return a dependency that passes only callers holding `role`."""

    # log.debug("Defines the dependency")
    def check(actor: Annotated[Actor, Depends(current_actor)]) -> Actor:
        """Return the caller if they hold the role.

        Raises:
            HTTPException: 403 without the role.
        """
        # log.debug("Refuses a caller without the role")
        if role not in actor.roles:
            # log.debug("Refuses with 403")
            raise _refuse(status.HTTP_403_FORBIDDEN, f"needs {role}")
        # log.debug("Returns the caller")
        return actor

    # log.debug("Returns the dependency")
    return check


# log.debug("Defines the dev sign-in")
def _dev_actor(user: str | None, role: str | None) -> Actor:
    """Return the actor the dev headers name.

    Raises:
        HTTPException: 401 when a header is missing or malformed.
    """
    # log.debug("Refuses missing or malformed headers")
    if user is None or role is None or not DEV_USER_RE.fullmatch(user) or role not in DEV_ROLES:
        # log.debug("Explains the headers dev mode needs")
        raise _refuse(
            status.HTTP_401_UNAUTHORIZED,
            "dev headers",
            "dev mode: send X-Dev-User (a name) and X-Dev-Role (requester or approver)",
        )
    # log.debug("Returns the actor, its id derived from the name")
    return Actor(
        user_id=f"dev:{user.strip().lower().replace(' ', '-')}",
        name=user.strip(),
        roles=frozenset({DEV_ROLES[role]}),
    )


# log.debug("Defines a logged refusal")
def _refuse(code: int, reason: str, detail: str = "") -> HTTPException:
    """Log the refusal's reason and return the HTTP error to raise."""
    # log.debug("Logs the reason, never a token")
    log_event(log, DENIED, logging.WARNING, status=code, reason=reason)
    # log.debug("Returns the error; 401s carry the sign-in challenge")
    return HTTPException(
        code,
        detail or ("sign in required" if code == status.HTTP_401_UNAUTHORIZED else "not allowed"),
        CHALLENGE if code == status.HTTP_401_UNAUTHORIZED else None,
    )
