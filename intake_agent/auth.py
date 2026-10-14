"""Who is calling, and what role do they hold.

Local development: the X-Role header (requester | approver) and an optional X-User header.
Enterprise identity: when ENTRA_TENANT_ID, ENTRA_CLIENT_ID and ENTRA_CLIENT_SECRET are set, bearer tokens from
Microsoft Entra ID are validated and roles are read from the token's `roles` claim (app roles named
`Intake.Requester` and `Intake.Approver`).

The Entra validation is a documented stub in v0.0: it refuses every token until the signature check is
implemented, so the fallback is never silently used in a configured environment.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException
from kds.settings import get_settings

ROLE_MAP = {"Intake.Requester": "requester", "Intake.Approver": "approver"}


@dataclass
class User:
    name: str
    roles: set[str]


def entra_enabled() -> bool:
    return get_settings().entra_configured


def _from_entra(authorization: str | None) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "bearer token required")
    # v0.1: fetch the tenant's JWKS, validate signature, audience (ENTRA_CLIENT_ID), issuer and expiry, then map
    # the `roles` claim through ROLE_MAP. Until then every token is refused so misconfiguration is loud.
    raise HTTPException(501, "Entra ID token validation is not implemented in this version")


def _from_header(x_role: str | None, x_user: str | None) -> User:
    role = (x_role or "requester").strip().lower()
    if role not in ("requester", "approver"):
        raise HTTPException(403, "X-Role must be requester or approver")
    return User(name=(x_user or f"dev-{role}").strip(), roles={role})


def any_role(
    authorization: str | None = Header(default=None),
    x_role: str | None = Header(default=None),
    x_user: str | None = Header(default=None),
) -> User:
    return _from_entra(authorization) if entra_enabled() else _from_header(x_role, x_user)


def require_role(role: str):
    def check(
        authorization: str | None = Header(default=None),
        x_role: str | None = Header(default=None),
        x_user: str | None = Header(default=None),
    ) -> User:
        user = any_role(authorization, x_role, x_user)
        if role not in user.roles:
            raise HTTPException(403, f"requires role {role}")
        return user

    return check
