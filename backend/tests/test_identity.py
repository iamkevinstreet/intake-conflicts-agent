########################################################################
#                    backend/tests/test_identity.py                    #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Tests sign-in: Entra ID token checks, the dev headers, and unsafe
settings refused.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

import time
from typing import Any

# Third-party
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from kds.args import required
from kds.logs import get_logger
from pydantic import ValidationError

# Local
from intake_agent.api.identity import EntraVerifier, _dev_actor
from intake_agent.config import AppSettings

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)

########################################################################
#                           Local constants                            #
########################################################################
# log.debug("Sets a made-up tenant id")
TENANT = "11111111-2222-3333-4444-555555555555"
# log.debug("Sets a made-up API client id, the audience")
AUDIENCE = "66666666-7777-8888-9999-000000000000"
# log.debug("Makes the signing key a real tenant would hold")
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
# log.debug("Makes a second key, which the tenant never published")
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


########################################################################
#                            Sign-in tests                             #
########################################################################
# log.debug("Defines the key source the tests hand the verifier")
class StaticKeys:
    """Always returns the tenant's public key."""

    # log.debug("Defines the lookup")
    def key_for(self, token: str | None = None) -> Any:
        """Returns the public key.

        Args:
            token: The access token; this source holds one key, so
                every token gets it. Required.

        Returns:
            The made-up tenant's public key.
        """
        # log.debug("Takes the token, which the caller must give")
        token = required(token=token)
        # log.debug("Returns it")
        return KEY.public_key()


# log.debug("Defines the verifier under test")
@pytest.fixture
def verifier() -> EntraVerifier:
    """A verifier for the made-up tenant.

    Returns:
        A token check with Entra ID settings for the made-up tenant and
        its key.
    """
    # log.debug("Builds Entra settings")
    settings = AppSettings(auth_mode="entra", entra_tenant_id=TENANT, entra_audience=AUDIENCE)
    # log.debug("Returns the verifier")
    return EntraVerifier(settings, StaticKeys())


# log.debug("Defines a token with any claims changed")
def token(key: Any = KEY, algorithm: str = "RS256", **changes: Any) -> str:
    """Returns a signed token for the made-up tenant, with `changes`.

    Args:
        key: The private key to sign with; the tenant's own by default.
        algorithm: The signing algorithm.
        **changes: Claims to change or add; a claim set to None is left
            out.

    Returns:
        The signed token.
    """
    # log.debug("Takes the time now")
    now = int(time.time())
    # log.debug("Builds the claims a real access token carries")
    claims = {
        "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0",
        "aud": AUDIENCE,
        "tid": TENANT,
        "oid": "aaaaaaaa-0000-0000-0000-000000000001",
        "name": "Jordan Reyes",
        "roles": ["Intake.Approver"],
        "iat": now,
        "nbf": now,
        "exp": now + 3600,
    } | changes
    # log.debug("Drops claims set to None")
    claims = {k: v for k, v in claims.items() if v is not None}
    # log.debug("Returns the signed token")
    return jwt.encode(claims, key, algorithm=algorithm)


# log.debug("Defines the valid-token test")
def test_a_valid_token_names_the_person_and_roles(verifier: EntraVerifier) -> None:
    """The object id, the name, and the role mapped to ours.

    Args:
        verifier: A token check for the test tenant and its keys.
    """
    # log.debug("Checks the actor")
    assert verifier.actor(token()).model_dump() == {
        "user_id": "aaaaaaaa-0000-0000-0000-000000000001",
        "name": "Jordan Reyes",
        "roles": frozenset({"approver"}),
    }


# log.debug("Defines the tokens that must be refused")
@pytest.mark.parametrize(
    "bad",
    [
        {"aud": "someone-else"},
        {"iss": "https://login.microsoftonline.com/another-tenant/v2.0"},
        {"tid": "99999999-2222-3333-4444-555555555555"},
        {"exp": int(time.time()) - 3600},
        {"oid": None},
    ],
)
def test_bad_claims_are_refused(verifier: EntraVerifier, bad: dict[str, Any]) -> None:
    """Wrong audience, issuer or tenant, expired, no oid: 401.

    Args:
        verifier: A token check for the test tenant and its keys.
        bad: Claims that must make the token fail.
    """
    # log.debug("Expects the refusal")
    with pytest.raises(HTTPException) as refused:
        # log.debug("Checks the token")
        verifier.actor(token(**bad))
    # log.debug("Checks it was 401")
    assert refused.value.status_code == 401


# log.debug("Defines the wrong-key test")
def test_a_token_signed_with_another_key_is_refused(verifier: EntraVerifier) -> None:
    """A forged signature fails.

    Args:
        verifier: A token check for the test tenant and its keys.
    """
    # log.debug("Expects the refusal")
    with pytest.raises(HTTPException):
        # log.debug("Checks a token the tenant did not sign")
        verifier.actor(token(key=OTHER_KEY))


# log.debug("Defines the algorithm-confusion test")
def test_an_hmac_token_is_refused(verifier: EntraVerifier) -> None:
    """HS256 signed with a guessable secret is not accepted, ever.

    Args:
        verifier: A token check for the test tenant and its keys.
    """
    # log.debug("Expects the refusal")
    with pytest.raises(HTTPException):
        # log.debug("Checks an HS256 token")
        verifier.actor(token(key="a-shared-secret-long-enough-for-hs256", algorithm="HS256"))


# log.debug("Defines the no-role test")
def test_a_signed_in_person_without_a_role_is_forbidden(verifier: EntraVerifier) -> None:
    """Signed in, but holding none of our app roles: 403.

    Args:
        verifier: A token check for the test tenant and its keys.
    """
    # log.debug("Expects the refusal")
    with pytest.raises(HTTPException) as refused:
        # log.debug("Checks a token with an unrelated role")
        verifier.actor(token(roles=["Payroll.Reader"]))
    # log.debug("Checks it was 403")
    assert refused.value.status_code == 403


# log.debug("Defines the dev-header tests")
def test_dev_headers() -> None:
    """A name and a role sign in; anything else is refused."""
    # log.debug("Checks a good pair")
    assert _dev_actor("Avery Stone", "requester").user_id == "dev:avery-stone"
    # log.debug("Checks each bad pair is refused")
    for user, role in [
        (None, "requester"),
        ("Avery", None),
        ("<script>", "approver"),
        ("A", "admin"),
    ]:
        # log.debug("Expects the refusal")
        with pytest.raises(HTTPException):
            # log.debug("Tries the pair")
            _dev_actor(user, role)


# log.debug("Defines the settings guards")
@pytest.mark.parametrize(
    "unsafe",
    [
        {"auth_mode": "dev", "api_host": "0.0.0.0"},  # noqa: S104 - the unsafe value under test
        {"auth_mode": "entra"},
        {"auth_mode": "entra", "entra_tenant_id": "not-a-guid", "entra_audience": AUDIENCE},
        {"match_likely": 80, "match_possible": 85},
    ],
)
def test_unsafe_settings_refuse_to_start(unsafe: dict[str, Any]) -> None:
    """Dev mode off this machine, no tenant, bad thresholds.

    Args:
        unsafe: Settings that must stop the service from starting.
    """
    # log.debug("Expects the refusal")
    with pytest.raises(ValidationError):
        # log.debug("Builds the settings")
        AppSettings(**unsafe)
