"""SQLite store for the intake prototype: clients, adverse parties, draft matters, approvals and the audit log.

The seed data is made up and salted with near duplicates so that fuzzy matching is tested, not assumed.
"""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from kds.synthetic.names import NameGen, near_duplicates

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS adverse_parties (id INTEGER PRIMARY KEY, name TEXT NOT NULL, client_id INTEGER, matter_ref TEXT);
CREATE TABLE IF NOT EXISTS drafts (
  id TEXT PRIMARY KEY, created_at TEXT NOT NULL, requester TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
  draft_id TEXT PRIMARY KEY, approver TEXT NOT NULL, decided_at TEXT NOT NULL, decision TEXT NOT NULL, note TEXT
);
CREATE TABLE IF NOT EXISTS matters (id INTEGER PRIMARY KEY, draft_id TEXT NOT NULL UNIQUE, opened_at TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, ts TEXT NOT NULL, actor TEXT NOT NULL, tool TEXT NOT NULL,
  args TEXT NOT NULL, result_hash TEXT, ok INTEGER NOT NULL, note TEXT
);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def seed(conn: sqlite3.Connection, *, n_clients: int = 400, seed: int = 11) -> dict[str, int]:
    """Fill the tables with made-up names. About a quarter of adverse parties are near duplicates of clients."""
    if conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]:
        return {"clients": 0, "adverse_parties": 0}
    rng = random.Random(seed)
    gen = NameGen(seed=seed)
    clients = []
    for _ in range(n_clients):
        name = gen.company() if rng.random() < 0.7 else gen.person()
        kind = (
            "company"
            if " " in name and name.split()[-1] in ("LLC", "Inc.", "Inc", "Corp.", "Co.", "LLP", "Group")
            else "person"
        )
        clients.append((name, kind))
    conn.executemany("INSERT INTO clients(name, kind) VALUES (?, ?)", clients)
    adverse = []
    rows = conn.execute("SELECT id, name FROM clients").fetchall()
    for row in rows:
        if rng.random() < 0.25:
            variants = near_duplicates(row["name"], rng)
            if variants:
                adverse.append((rng.choice(variants), row["id"], f"M-{rng.randint(1000, 9999)}"))
        if rng.random() < 0.3:
            adverse.append((gen.company(), None, f"M-{rng.randint(1000, 9999)}"))
    conn.executemany("INSERT INTO adverse_parties(name, client_id, matter_ref) VALUES (?, ?, ?)", adverse)
    conn.commit()
    return {"clients": len(clients), "adverse_parties": len(adverse)}


def audit(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    actor: str,
    tool: str,
    args: dict,
    result_hash: str | None,
    ok: bool,
    note: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO audit(run_id, ts, actor, tool, args, result_hash, ok, note) VALUES (?,?,?,?,?,?,?,?)",
        (
            run_id,
            datetime.now(UTC).isoformat(timespec="milliseconds"),
            actor,
            tool,
            json.dumps(args),
            result_hash,
            int(ok),
            note,
        ),
    )
    conn.commit()
