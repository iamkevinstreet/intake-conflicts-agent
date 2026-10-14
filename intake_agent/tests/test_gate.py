"""The one test that must never go red: a matter cannot be opened without an approval record."""

import pytest
from fastapi.testclient import TestClient

from intake_agent.db import connect, seed
from intake_agent.tools import GateError, Tools, approve


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "t.sqlite")
    seed(c, n_clients=40)
    yield c
    c.close()


def test_open_matter_refuses_without_approval(conn):
    tools = Tools(conn, run_id="R-test", actor="agent")
    draft = tools.draft_matter(
        client="X", adverse_parties=[], matter_type="t", summary="s", conflicts=[], needs_human_review=False
    )
    with pytest.raises(GateError):
        tools.open_matter(draft["draft_id"])
    refused = conn.execute("SELECT note FROM audit WHERE tool='open_matter' AND ok=0").fetchall()
    assert refused and "refused" in refused[0]["note"]
    assert conn.execute("SELECT COUNT(*) FROM matters").fetchone()[0] == 0


def test_open_matter_refuses_after_rejection(conn):
    tools = Tools(conn, run_id="R-test", actor="agent")
    draft = tools.draft_matter(
        client="X", adverse_parties=[], matter_type="t", summary="s", conflicts=[], needs_human_review=False
    )
    approve(conn, draft_id=draft["draft_id"], approver="boss", decision="rejected")
    with pytest.raises(GateError):
        tools.open_matter(draft["draft_id"])


def test_open_matter_succeeds_only_after_approval(conn):
    tools = Tools(conn, run_id="R-test", actor="agent")
    draft = tools.draft_matter(
        client="X", adverse_parties=[], matter_type="t", summary="s", conflicts=[], needs_human_review=False
    )
    approve(conn, draft_id=draft["draft_id"], approver="boss", decision="approved")
    out = tools.open_matter(draft["draft_id"])
    assert out["matter_id"] >= 1
    assert (
        conn.execute("SELECT status FROM drafts WHERE id=?", (draft["draft_id"],)).fetchone()["status"]
        == "opened"
    )


def test_fuzzy_search_finds_near_duplicates(conn):
    conn.execute(
        "INSERT INTO adverse_parties(name, client_id, matter_ref) VALUES ('Acme Logistic Inc', NULL, 'M-1')"
    )
    conn.commit()
    tools = Tools(conn, run_id="R-test", actor="agent")
    hits = tools.search_adverse_parties("ACME Logistics LLC")
    match = next((h for h in hits if h["name"] == "Acme Logistic Inc"), None)
    assert match is not None and match["score"] >= 60


def test_api_roles_and_gate(tmp_path, monkeypatch):
    from intake_agent import api

    monkeypatch.setattr(api, "DB_PATH", tmp_path / "api.sqlite")
    client = TestClient(api.app)
    assert client.get("/health").json()["identity"] == "header"
    # a requester cannot decide, and nobody can open without a decision
    c = connect(tmp_path / "api.sqlite")
    seed(c, n_clients=10)
    draft = Tools(c, run_id="R-api", actor="dev").draft_matter(
        client="X", adverse_parties=[], matter_type="t", summary="s", conflicts=[], needs_human_review=False
    )
    c.close()
    assert (
        client.post(
            f"/drafts/{draft['draft_id']}/decision",
            json={"decision": "approved"},
            headers={"X-Role": "requester"},
        ).status_code
        == 403
    )
    assert client.post(f"/drafts/{draft['draft_id']}/open", headers={"X-Role": "approver"}).status_code == 409
    assert (
        client.post(
            f"/drafts/{draft['draft_id']}/decision",
            json={"decision": "approved"},
            headers={"X-Role": "approver"},
        ).status_code
        == 200
    )
    assert client.post(f"/drafts/{draft['draft_id']}/open", headers={"X-Role": "approver"}).status_code == 200
