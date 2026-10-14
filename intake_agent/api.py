"""Intake service with two roles. Requesters run intake; approvers decide; opening a matter needs an approval row.

    uvicorn intake_agent.api:app --reload

Roles: when ENTRA_* settings are present, `auth.py` validates Microsoft Entra ID tokens and reads app roles.
Otherwise the X-Role header stands in for local development.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from kds.llm.adapter import get_adapter
from pydantic import BaseModel

from intake_agent import auth
from intake_agent.agent import RunOutcome, new_run_id, run_intake
from intake_agent.db import connect, seed
from intake_agent.tools import GateError, Tools, approve

DB_PATH = Path(__file__).resolve().parent / "data" / "generated" / "intake.sqlite"
app = FastAPI(title="New-matter intake agent", version="0.1.0")


def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(DB_PATH)
    seed(conn)
    try:
        yield conn
    finally:
        conn.close()


class IntakeIn(BaseModel):
    email_text: str


class DecisionIn(BaseModel):
    decision: str
    note: str | None = None


@app.get("/health")
def health() -> dict:
    return {"ok": True, "identity": "entra" if auth.entra_enabled() else "header"}


@app.post("/intake", response_model=RunOutcome)
def intake(
    body: IntakeIn, user: auth.User = Depends(auth.require_role("requester")), conn=Depends(db)
) -> RunOutcome:
    tools = Tools(conn, run_id=new_run_id(), actor=user.name)
    return run_intake(get_adapter(), tools, body.email_text)


@app.get("/drafts/{draft_id}")
def get_draft(draft_id: str, user: auth.User = Depends(auth.any_role), conn=Depends(db)) -> dict:
    row = conn.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "no such draft")
    return {
        "id": row["id"],
        "status": row["status"],
        "requester": row["requester"],
        "payload": json.loads(row["payload"]),
    }


@app.post("/drafts/{draft_id}/decision")
def decide(
    draft_id: str,
    body: DecisionIn,
    user: auth.User = Depends(auth.require_role("approver")),
    conn=Depends(db),
) -> dict:
    if conn.execute("SELECT 1 FROM drafts WHERE id=?", (draft_id,)).fetchone() is None:
        raise HTTPException(404, "no such draft")
    approve(conn, draft_id=draft_id, approver=user.name, decision=body.decision, note=body.note)
    return {"draft_id": draft_id, "decision": body.decision}


@app.post("/drafts/{draft_id}/open")
def open_matter(
    draft_id: str, user: auth.User = Depends(auth.require_role("approver")), conn=Depends(db)
) -> dict:
    tools = Tools(conn, run_id=new_run_id(), actor=user.name)
    try:
        return tools.open_matter(draft_id)
    except GateError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/audit/{run_id}")
def audit_trail(run_id: str, user: auth.User = Depends(auth.any_role), conn=Depends(db)) -> list[dict]:
    rows = conn.execute("SELECT * FROM audit WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    return [dict(r) | {"args": json.loads(r["args"])} for r in rows]
