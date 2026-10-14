"""The agent's tools. Search is read only, drafting writes to staging, and open_matter is gated by an approval
record that only an approver can create. The gate is checked here, in code the model cannot reach."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any

from kds.llm.types import ToolSpec
from kds.logs.redact import redact_obj
from rapidfuzz import fuzz, process

from intake_agent.db import audit


class GateError(PermissionError):
    """Raised when open_matter is called without an approval. The test suite asserts this is always raised."""


TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name="search_clients",
        description="Fuzzy search current and former clients by name. Read only. Returns matches with a similarity score 0-100.",
        parameters={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    ),
    ToolSpec(
        name="search_adverse_parties",
        description="Fuzzy search parties the firm has been adverse to. Read only. Returns matches with a similarity score 0-100.",
        parameters={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    ),
    ToolSpec(
        name="draft_matter",
        description="Save a draft matter to staging. It is not opened. Include every party and the conflict findings.",
        parameters={
            "type": "object",
            "properties": {
                "client": {"type": "string"},
                "adverse_parties": {"type": "array", "items": {"type": "string"}},
                "matter_type": {"type": "string"},
                "summary": {"type": "string"},
                "conflicts": {"type": "array", "items": {"type": "object"}},
                "needs_human_review": {"type": "boolean"},
            },
            "required": [
                "client",
                "adverse_parties",
                "matter_type",
                "summary",
                "conflicts",
                "needs_human_review",
            ],
        },
    ),
    ToolSpec(
        name="request_approval",
        description="Ask an approver to review a draft. Ends the agent's work; a person decides next.",
        parameters={
            "type": "object",
            "properties": {"draft_id": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["draft_id", "reason"],
        },
    ),
    ToolSpec(
        name="open_matter",
        description="Open a matter from an approved draft. Fails unless an approver has approved the draft.",
        parameters={
            "type": "object",
            "properties": {"draft_id": {"type": "string"}},
            "required": ["draft_id"],
        },
    ),
]


class Tools:
    def __init__(self, conn: sqlite3.Connection, *, run_id: str, actor: str):
        self.conn = conn
        self.run_id = run_id
        self.actor = actor

    # ----- read only ---------------------------------------------------------------------------------

    def search_clients(self, name: str, limit: int = 5) -> list[dict[str, Any]]:
        return self._search("clients", name, limit)

    def search_adverse_parties(self, name: str, limit: int = 5) -> list[dict[str, Any]]:
        return self._search("adverse_parties", name, limit)

    def _search(self, table: str, name: str, limit: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(f"SELECT id, name FROM {table}").fetchall()  # noqa: S608 - table is a literal above
        choices = {r["id"]: r["name"] for r in rows}
        hits = process.extract(name, choices, scorer=fuzz.token_set_ratio, limit=limit)
        out = [{"id": key, "name": match, "score": int(score)} for match, score, key in hits if score >= 60]
        self._audit("search_" + table, {"name": name}, out, ok=True)
        return out

    # ----- staging write -----------------------------------------------------------------------------

    def draft_matter(self, **payload: Any) -> dict[str, Any]:
        draft_id = "D-" + uuid.uuid4().hex[:8]
        self.conn.execute(
            "INSERT INTO drafts(id, created_at, requester, payload, status) VALUES (?,?,?,?,?)",
            (
                draft_id,
                datetime.now(UTC).isoformat(timespec="seconds"),
                self.actor,
                json.dumps(payload),
                "draft",
            ),
        )
        self.conn.commit()
        out = {"draft_id": draft_id, "status": "draft"}
        self._audit("draft_matter", payload, out, ok=True)
        return out

    def request_approval(self, draft_id: str, reason: str) -> dict[str, Any]:
        self.conn.execute("UPDATE drafts SET status='pending_approval' WHERE id=?", (draft_id,))
        self.conn.commit()
        out = {"draft_id": draft_id, "status": "pending_approval"}
        self._audit("request_approval", {"draft_id": draft_id, "reason": reason}, out, ok=True)
        return out

    # ----- gated -------------------------------------------------------------------------------------

    def open_matter(self, draft_id: str) -> dict[str, Any]:
        row = self.conn.execute("SELECT decision FROM approvals WHERE draft_id=?", (draft_id,)).fetchone()
        if row is None or row["decision"] != "approved":
            self._audit(
                "open_matter", {"draft_id": draft_id}, None, ok=False, note="refused: no approval record"
            )
            raise GateError(f"draft {draft_id} has no approval")
        draft = self.conn.execute("SELECT payload FROM drafts WHERE id=?", (draft_id,)).fetchone()
        if draft is None:
            raise GateError(f"draft {draft_id} does not exist")
        cur = self.conn.execute(
            "INSERT INTO matters(draft_id, opened_at, payload) VALUES (?,?,?)",
            (draft_id, datetime.now(UTC).isoformat(timespec="seconds"), draft["payload"]),
        )
        self.conn.execute("UPDATE drafts SET status='opened' WHERE id=?", (draft_id,))
        self.conn.commit()
        out = {"matter_id": cur.lastrowid, "draft_id": draft_id}
        self._audit("open_matter", {"draft_id": draft_id}, out, ok=True)
        return out

    # ----- dispatch and audit ------------------------------------------------------------------------

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any] | list[dict[str, Any]]:
        fn = {
            "search_clients": self.search_clients,
            "search_adverse_parties": self.search_adverse_parties,
            "draft_matter": self.draft_matter,
            "request_approval": self.request_approval,
            "open_matter": self.open_matter,
        }.get(name)
        if fn is None:
            self._audit(name, arguments, None, ok=False, note="unknown tool")
            raise ValueError(f"unknown tool {name}")
        return fn(**arguments)

    def _audit(self, tool: str, args: dict, result: Any, *, ok: bool, note: str | None = None) -> None:
        digest = (
            hashlib.sha256(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()[:16]
            if result is not None
            else None
        )
        audit(
            self.conn,
            run_id=self.run_id,
            actor=self.actor,
            tool=tool,
            args=redact_obj(args),
            result_hash=digest,
            ok=ok,
            note=note,
        )


def approve(
    conn: sqlite3.Connection, *, draft_id: str, approver: str, decision: str, note: str | None = None
) -> None:
    """Only the API's approver-role endpoint calls this. The agent has no tool for it."""
    if decision not in ("approved", "rejected"):
        raise ValueError("decision must be approved or rejected")
    conn.execute(
        "INSERT OR REPLACE INTO approvals(draft_id, approver, decided_at, decision, note) VALUES (?,?,?,?,?)",
        (draft_id, approver, datetime.now(UTC).isoformat(timespec="seconds"), decision, note),
    )
    conn.execute("UPDATE drafts SET status=? WHERE id=?", (decision, draft_id))
    conn.commit()
