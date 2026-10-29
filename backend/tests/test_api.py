########################################################################
#                      backend/tests/test_api.py                       #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           Tests the HTTP service: roles, the gate's        #
#                     routes, scoping, limits, hosts and headers.      #
########################################################################
"""Tests for the HTTP service: roles, gate routes, limits, headers."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kds.llm import ModelAdapter
from kds.logs import get_logger

from intake_agent.api.app import create_app
from intake_agent.config import AppSettings

from support import CONFLICT_EMAIL, good_turns, scripted, submit

# Module constants
log = get_logger(__name__)
# log.debug("Sets the headers of the requester")
AVERY = {"X-Dev-User": "Avery Stone", "X-Dev-Role": "requester"}
# log.debug("Sets the headers of a second requester")
CASEY = {"X-Dev-User": "Casey Lin", "X-Dev-Role": "requester"}
# log.debug("Sets the headers of an approver")
JORDAN = {"X-Dev-User": "Jordan Reyes", "X-Dev-Role": "approver"}
# log.debug("Sets a reason long enough to approve past a flag")
REASON = {"decision": "approved", "note": "Waiver signed by both clients, on file."}


# log.debug("Defines a client around an app with a scripted model")
def _client(settings: AppSettings, adapter: ModelAdapter) -> Iterator[TestClient]:
    """Yield a test client addressed to this machine, started up."""
    # log.debug("Starts the app and yields the client")
    with TestClient(create_app(settings, adapter=adapter), base_url="http://127.0.0.1") as client:
        # log.debug("Yields it")
        yield client


# log.debug("Defines the client most tests use: one good run is scripted")
@pytest.fixture
def client(settings: AppSettings) -> Iterator[TestClient]:
    """A client whose model searches, drafts and submits once."""
    # log.debug("Yields it")
    yield from _client(settings, scripted(settings, *good_turns(), responder=submit))


# log.debug("Defines a submitted intake")
def _intake(client: TestClient) -> dict[str, Any]:
    """Run the scripted intake as Avery and return the response body."""
    # log.debug("Posts the email")
    response = client.post("/api/v1/intake", json={"email": CONFLICT_EMAIL}, headers=AVERY)
    # log.debug("Checks it was created")
    assert response.status_code == 201, response.text
    # log.debug("Returns the body")
    return dict(response.json())


# log.debug("Defines the health test")
def test_health(client: TestClient) -> None:
    """Open to monitors; says the mode and the firm's size."""
    # log.debug("Reads the health report")
    body = client.get("/api/v1/health").json()
    # log.debug("Checks the mode and the counts")
    assert (body["auth_mode"], body["firm"]["clients"]) == ("dev", 300)


# log.debug("Defines the sign-in test")
def test_routes_need_a_signed_in_person(client: TestClient) -> None:
    """Without the dev headers, 401 with a sign-in challenge."""
    # log.debug("Asks for the runs anonymously")
    response = client.get("/api/v1/runs")
    # log.debug("Checks the refusal and the challenge")
    assert (response.status_code, response.headers["WWW-Authenticate"]) == (401, "Bearer")


# log.debug("Defines the role test for intake")
def test_only_requesters_run_intakes(client: TestClient) -> None:
    """An approver who is not a requester gets 403."""
    # log.debug("Posts as the approver")
    response = client.post("/api/v1/intake", json={"email": CONFLICT_EMAIL}, headers=JORDAN)
    # log.debug("Checks the refusal")
    assert response.status_code == 403


# log.debug("Defines the whole flow through the API")
def test_intake_review_approve_open(client: TestClient) -> None:
    """Submit, open early (409), approve with a reason, open (201)."""
    # log.debug("Runs the intake")
    draft_id = _intake(client)["draft"]["draft"]["id"]
    # log.debug("Tries to open before any approval")
    early = client.post(f"/api/v1/drafts/{draft_id}/open", headers=JORDAN)
    # log.debug("Approves with a reason")
    approved = client.post(f"/api/v1/drafts/{draft_id}/decision", json=REASON, headers=JORDAN)
    # log.debug("Opens it")
    opened = client.post(f"/api/v1/drafts/{draft_id}/open", headers=JORDAN)
    # log.debug("Checks each status and the matter number")
    assert (
        early.status_code,
        approved.status_code,
        opened.status_code,
        opened.json()["number"],
    ) == (
        409,
        200,
        201,
        "NM-00001",
    )


# log.debug("Defines the decision refusals")
def test_decision_refusals(client: TestClient) -> None:
    """A requester cannot decide (403); a flag needs a reason (422)."""
    # log.debug("Runs the intake")
    draft_id = _intake(client)["draft"]["draft"]["id"]
    # log.debug("Tries to decide as the requester")
    as_requester = client.post(f"/api/v1/drafts/{draft_id}/decision", json=REASON, headers=AVERY)
    # log.debug("Tries to approve with no reason")
    no_reason = client.post(
        f"/api/v1/drafts/{draft_id}/decision", json={"decision": "approved"}, headers=JORDAN
    )
    # log.debug("Checks both refusals")
    assert (as_requester.status_code, no_reason.status_code) == (403, 422)


# log.debug("Defines the scoping test")
def test_requesters_see_only_their_own(client: TestClient) -> None:
    """Another requester gets 404s and empty lists."""
    # log.debug("Runs the intake as Avery")
    body = _intake(client)
    # log.debug("Reads Avery's draft as Casey")
    draft = client.get(f"/api/v1/drafts/{body['draft']['draft']['id']}", headers=CASEY)
    # log.debug("Reads Avery's run as Casey")
    run = client.get(f"/api/v1/runs/{body['run']['id']}", headers=CASEY)
    # log.debug("Lists the drafts as Casey and as the approver")
    lists = [len(client.get("/api/v1/drafts", headers=h).json()) for h in (CASEY, JORDAN)]
    # log.debug("Checks both are hidden from Casey and visible to the approver")
    assert (draft.status_code, run.status_code, lists) == (404, 404, [0, 1])


# log.debug("Defines the audit-trail test")
def test_the_run_detail_shows_every_call(client: TestClient) -> None:
    """Four tool calls and three model calls, in order."""
    # log.debug("Runs the intake")
    run_id = _intake(client)["run"]["id"]
    # log.debug("Reads the run's detail")
    detail = client.get(f"/api/v1/runs/{run_id}", headers=AVERY).json()
    # log.debug("Checks the calls")
    assert ([c["tool"] for c in detail["tool_calls"]], len(detail["model_calls"])) == (
        ["search_adverse_parties", "search_clients", "draft_matter", "request_approval"],
        3,
    )


# log.debug("Defines the path-safety test")
@pytest.mark.parametrize("path", ["/api/v1/drafts/D-..%2F..%2Fetc", "/api/v1/runs/R-1"])
def test_malformed_ids_are_refused(client: TestClient, path: str) -> None:
    """Ids that do not match their pattern never reach the database."""
    # log.debug("Asks for it")
    response = client.get(path, headers=JORDAN)
    # log.debug("Checks it was refused as invalid")
    assert response.status_code in (404, 422)


# log.debug("Defines the rate-limit test")
def test_intakes_are_rate_limited(settings: AppSettings) -> None:
    """Past the per-minute limit, 429 with a retry hint."""
    # log.debug("Allows one intake a minute")
    limited = settings.model_copy(update={"api_intakes_per_minute": 1})
    # log.debug("Starts a client with a model that just talks")
    for client in _client(limited, scripted(limited, "Nothing to do.", "Nothing to do.")):
        # log.debug("Runs one intake")
        client.post("/api/v1/intake", json={"email": CONFLICT_EMAIL}, headers=AVERY)
        # log.debug("Runs a second")
        second = client.post("/api/v1/intake", json={"email": CONFLICT_EMAIL}, headers=AVERY)
        # log.debug("Checks the refusal")
        assert (second.status_code, second.headers["Retry-After"]) == (429, "60")


# log.debug("Defines the size tests")
def test_email_size_limits(client: TestClient) -> None:
    """Too short: 422. Over the body limit: 413, before it is read."""
    # log.debug("Posts a short email")
    short = client.post("/api/v1/intake", json={"email": "hi"}, headers=AVERY)
    # log.debug("Posts a huge body")
    huge = client.post("/api/v1/intake", json={"email": "x" * 200_000}, headers=AVERY)
    # log.debug("Checks both")
    assert (short.status_code, huge.status_code) == (422, 413)


# log.debug("Defines the header test")
def test_security_headers_and_request_id(client: TestClient) -> None:
    """Every response has the headers and echoes a good request id."""
    # log.debug("Asks with a request id")
    response = client.get("/api/v1/health", headers={"X-Request-ID": "abc-123"})
    # log.debug("Checks the headers")
    assert (
        response.headers["X-Request-ID"],
        response.headers["X-Frame-Options"],
        response.headers["Cache-Control"],
    ) == ("abc-123", "DENY", "no-store")


# log.debug("Defines the host test")
def test_requests_for_another_host_are_refused(client: TestClient) -> None:
    """A rebinding page gets 400, still with the headers."""
    # log.debug("Asks with a foreign Host header")
    response = client.get("/api/v1/health", headers={"Host": "attacker.example"})
    # log.debug("Checks the refusal still carries the request id and headers")
    assert (
        response.status_code,
        "X-Request-ID" in response.headers,
        response.headers.get("X-Frame-Options"),
    ) == (400, True, "DENY")


# log.debug("Defines the test for a body that hides its length")
def test_a_body_without_a_declared_length_is_refused(client: TestClient) -> None:
    """A chunked body cannot be measured unread, so it gets 411."""
    # log.debug("Sends the email as a stream, which has no Content-Length")
    response = client.post(
        "/api/v1/intake",
        content=iter([b'{"email": "', b"x" * 50, b'"}']),
        headers={**AVERY, "Content-Type": "application/json"},
    )
    # log.debug("Checks the refusal")
    assert response.status_code == 411


# log.debug("Defines the test for an error nobody planned for")
def test_an_unplanned_error_is_a_plain_500_with_headers(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reply says nothing about the error and keeps the headers."""

    # log.debug("Defines a failing read of the runs")
    def broken(**_: Any) -> Any:
        """Fail.

        Raises:
            RuntimeError: Always.
        """
        # log.debug("Raises the failure")
        raise RuntimeError("disk on fire")

    # log.debug("Takes the app the client serves")
    app: Any = client.app
    # log.debug("Makes listing runs fail")
    monkeypatch.setattr(app.state.services.runlog, "runs", broken)
    # log.debug("Asks for the runs")
    response = client.get("/api/v1/runs", headers=AVERY)
    # log.debug("Checks the reply")
    assert (
        response.status_code,
        response.json(),
        "X-Request-ID" in response.headers,
    ) == (500, {"detail": "internal error"}, True)


# log.debug("Defines the note limit test")
def test_a_note_over_the_limit_is_refused(client: TestClient, settings: AppSettings) -> None:
    """The setting, not a hard-coded number, limits a decision note."""
    # log.debug("Runs the intake")
    draft_id = _intake(client)["draft"]["draft"]["id"]
    # log.debug("Approves with a note one character over the setting")
    response = client.post(
        f"/api/v1/drafts/{draft_id}/decision",
        json={"decision": "approved", "note": "x" * (settings.api_max_note_chars + 1)},
        headers=JORDAN,
    )
    # log.debug("Checks the refusal names the limit")
    assert (response.status_code, str(settings.api_max_note_chars) in response.text) == (
        422,
        True,
    )


# log.debug("Defines the examples test")
def test_examples_come_from_the_scenarios(client: TestClient) -> None:
    """The four examples settings name, with their emails."""
    # log.debug("Reads the examples")
    examples = client.get("/api/v1/examples", headers=AVERY).json()
    # log.debug("Checks their ids")
    assert [e["id"] for e in examples] == ["s04", "s09", "s13", "s18"]
