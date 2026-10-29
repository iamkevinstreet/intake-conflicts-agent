########################################################################
#                backend/src/intake_agent/core/store.py                #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Opens the SQLite database and keeps its schema, migrations and the
triggers that hold the gate and the audit rules. The schema carries the
rules that must hold even if the Python above it has a bug: a new matter
cannot be inserted without an approval record, a requester cannot
approve their own draft, a draft's text cannot change once saved, and
the audit records cannot be edited or deleted. Schema changes arrive
only as numbered migrations.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

# Third-party
from kds.args import required
from kds.logs import get_logger, log_event

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)

########################################################################
#                           Local constants                            #
########################################################################
# log.debug("Lists the migrations in order; the database records how many have run")
MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE clients (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('current', 'former'))
    );
    CREATE TABLE matters (
        id INTEGER PRIMARY KEY,
        number TEXT NOT NULL UNIQUE,
        client_id INTEGER NOT NULL REFERENCES clients (id),
        kind TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('open', 'closed'))
    );
    CREATE TABLE adverse_parties (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        matter_id INTEGER NOT NULL REFERENCES matters (id)
    );
    CREATE TABLE drafts (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        requester TEXT NOT NULL,
        created_at TEXT NOT NULL,
        body TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        status TEXT NOT NULL
            CHECK (status IN ('draft', 'pending', 'approved', 'rejected', 'opened')),
        note TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE approvals (
        draft_id TEXT PRIMARY KEY REFERENCES drafts (id),
        approver TEXT NOT NULL,
        approver_name TEXT NOT NULL,
        decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
        note TEXT NOT NULL,
        draft_sha256 TEXT NOT NULL,
        decided_at TEXT NOT NULL
    );
    CREATE TABLE new_matters (
        id INTEGER PRIMARY KEY,
        draft_id TEXT NOT NULL UNIQUE REFERENCES drafts (id),
        opened_by TEXT NOT NULL,
        opened_by_name TEXT NOT NULL,
        opened_at TEXT NOT NULL
    );
    CREATE TABLE runs (
        id TEXT PRIMARY KEY,
        requester TEXT NOT NULL,
        requester_name TEXT NOT NULL,
        started_at TEXT NOT NULL,
        email_sha256 TEXT NOT NULL,
        email_chars INTEGER NOT NULL,
        model TEXT NOT NULL,
        outcome TEXT NOT NULL DEFAULT 'running'
            CHECK (outcome IN ('running', 'submitted', 'no_draft', 'incomplete', 'failed')),
        reason TEXT NOT NULL DEFAULT '',
        draft_id TEXT,
        steps INTEGER NOT NULL DEFAULT 0,
        tool_calls INTEGER NOT NULL DEFAULT 0,
        input_tokens INTEGER NOT NULL DEFAULT 0,
        output_tokens INTEGER NOT NULL DEFAULT 0,
        cost_usd REAL,
        ms INTEGER NOT NULL DEFAULT 0,
        finished_at TEXT
    );
    CREATE TABLE model_calls (
        run_id TEXT NOT NULL REFERENCES runs (id),
        step INTEGER NOT NULL,
        input_tokens INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,
        cost_usd REAL,
        ms INTEGER NOT NULL,
        stop_reason TEXT NOT NULL,
        PRIMARY KEY (run_id, step)
    );
    CREATE TABLE tool_calls (
        run_id TEXT NOT NULL REFERENCES runs (id),
        seq INTEGER NOT NULL,
        step INTEGER NOT NULL,
        tool TEXT NOT NULL,
        arguments TEXT NOT NULL,
        ok INTEGER NOT NULL CHECK (ok IN (0, 1)),
        error TEXT NOT NULL,
        result_sha256 TEXT NOT NULL,
        ms INTEGER NOT NULL,
        at TEXT NOT NULL,
        PRIMARY KEY (run_id, seq)
    );
    CREATE INDEX runs_by_requester ON runs (requester, started_at);
    CREATE INDEX drafts_by_status ON drafts (status, created_at);
    CREATE INDEX adverse_by_matter ON adverse_parties (matter_id);

    CREATE TRIGGER new_matters_need_approval BEFORE INSERT ON new_matters
    WHEN NOT EXISTS (
        SELECT 1 FROM approvals WHERE draft_id = NEW.draft_id AND decision = 'approved'
    )
    BEGIN SELECT RAISE(ABORT, 'no approval record for this draft'); END;

    CREATE TRIGGER approvals_only_pending BEFORE INSERT ON approvals
    WHEN (SELECT status FROM drafts WHERE id = NEW.draft_id) IS NOT 'pending'
    BEGIN SELECT RAISE(ABORT, 'only a draft awaiting approval can be decided'); END;

    CREATE TRIGGER approvals_not_by_requester BEFORE INSERT ON approvals
    WHEN NEW.approver = (SELECT requester FROM drafts WHERE id = NEW.draft_id)
    BEGIN SELECT RAISE(ABORT, 'a requester cannot decide their own draft'); END;

    CREATE TRIGGER approvals_match_draft BEFORE INSERT ON approvals
    WHEN NEW.draft_sha256 IS NOT (SELECT sha256 FROM drafts WHERE id = NEW.draft_id)
    BEGIN SELECT RAISE(ABORT, 'the approval does not match the saved draft'); END;

    CREATE TRIGGER drafts_text_frozen BEFORE UPDATE OF body, sha256, requester, run_id ON drafts
    BEGIN SELECT RAISE(ABORT, 'a saved draft cannot be rewritten'); END;

    CREATE TRIGGER drafts_no_delete BEFORE DELETE ON drafts
    BEGIN SELECT RAISE(ABORT, 'these records cannot be changed or deleted'); END;
    CREATE TRIGGER approvals_no_update BEFORE UPDATE ON approvals
    BEGIN SELECT RAISE(ABORT, 'these records cannot be changed or deleted'); END;
    CREATE TRIGGER approvals_no_delete BEFORE DELETE ON approvals
    BEGIN SELECT RAISE(ABORT, 'these records cannot be changed or deleted'); END;
    CREATE TRIGGER new_matters_no_update BEFORE UPDATE ON new_matters
    BEGIN SELECT RAISE(ABORT, 'these records cannot be changed or deleted'); END;
    CREATE TRIGGER new_matters_no_delete BEFORE DELETE ON new_matters
    BEGIN SELECT RAISE(ABORT, 'these records cannot be changed or deleted'); END;
    CREATE TRIGGER runs_no_delete BEFORE DELETE ON runs
    BEGIN SELECT RAISE(ABORT, 'these records cannot be changed or deleted'); END;
    CREATE TRIGGER runs_finish_once BEFORE UPDATE ON runs WHEN OLD.outcome != 'running'
    BEGIN SELECT RAISE(ABORT, 'these records cannot be changed or deleted'); END;
    CREATE TRIGGER model_calls_no_update BEFORE UPDATE ON model_calls
    BEGIN SELECT RAISE(ABORT, 'these records cannot be changed or deleted'); END;
    CREATE TRIGGER model_calls_no_delete BEFORE DELETE ON model_calls
    BEGIN SELECT RAISE(ABORT, 'these records cannot be changed or deleted'); END;
    CREATE TRIGGER tool_calls_no_update BEFORE UPDATE ON tool_calls
    BEGIN SELECT RAISE(ABORT, 'these records cannot be changed or deleted'); END;
    CREATE TRIGGER tool_calls_no_delete BEFORE DELETE ON tool_calls
    BEGIN SELECT RAISE(ABORT, 'these records cannot be changed or deleted'); END;
    """,
)


########################################################################
#                            Firm database                             #
########################################################################
# log.debug("Defines the clock every record is stamped with: UTC, to the second")
def utc_now() -> str:
    """Returns the time now in UTC, as ISO 8601 to the second.

    Returns:
        The time, such as 2026-10-29T14:49:59+00:00.
    """
    # log.debug("Returns the time")
    return datetime.now(UTC).isoformat(timespec="seconds")


# log.debug("Defines record ids: a prefix and ten random hex digits")
def new_id(prefix: str | None = None) -> str:
    """Returns a new id such as D-3f9a1c0b7e, unguessable and short.

    Args:
        prefix: The letter that says what the id names: D for a draft,
            R for a run. Required.

    Returns:
        The prefix, a hyphen and ten random hex digits.
    """
    # log.debug("Takes the prefix, which the caller must give")
    prefix = required(prefix=prefix)
    # log.debug("Returns the prefix and the first ten hex digits of a random UUID")
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


# log.debug("Defines the error a timed-out or locked read raises")
class StoreTimeoutError(RuntimeError):
    """The database did not answer in time; a retry may succeed."""


# log.debug("Defines the database")
class Store:
    """One SQLite file. Each unit of work opens its own connection."""

    # log.debug("Defines the constructor")
    def __init__(self, path: Path | None = None, *, timeout_s: float | None = None) -> None:
        """Opens or creates the database at `path` and migrates it.

        Args:
            path: The database file; its folder is created if missing.
                Required.
            timeout_s: How long a query waits on a locked database.
                Required.
        """
        # log.debug("Takes the path, which the caller must give")
        path = required(path=path)
        # log.debug("Takes the wait for a locked database, which the caller must give")
        timeout_s = required(timeout_s=timeout_s)
        # log.debug("Keeps the path")
        self.path = path
        # log.debug("Keeps the wait for a locked database")
        self.timeout_s = timeout_s
        # log.debug("Creates the folder the file lives in")
        path.parent.mkdir(parents=True, exist_ok=True)
        # log.debug("Brings the schema up to date")
        self._migrate()

    # log.debug("Defines a unit of work: one connection, committed or rolled back")
    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yields a connection; commits on success, rolls back on error.

        Yields:
            The open connection, its rows readable by column name and
            its foreign keys on.

        Raises:
            StoreTimeoutError: The database stayed locked past the
                timeout, which a caller may retry.
        """
        # log.debug("Opens the connection, closing it however the work ends")
        with closing(sqlite3.connect(self.path, timeout=self.timeout_s)) as connection:
            # log.debug("Returns rows that can be read by column name")
            connection.row_factory = sqlite3.Row
            # log.debug("Turns on foreign keys, which SQLite leaves off by default")
            connection.execute("PRAGMA foreign_keys = ON")
            # log.debug("Runs the work as one transaction")
            try:
                # log.debug("Hands the connection to the work")
                with connection:
                    # log.debug("Yields it")
                    yield connection
            except sqlite3.OperationalError as error:
                # log.debug("Reports a locked or busy database as a timeout")
                if "locked" in str(error) or "busy" in str(error):
                    # log.debug("Raises the timeout, keeping the cause")
                    raise StoreTimeoutError(str(error)) from error
                # log.debug("Raises any other error unchanged")
                raise

    # log.debug("Defines the migration step")
    def _migrate(self) -> None:
        """Runs each migration this file lacks, each atomically."""
        # log.debug("Opens the database for the schema change")
        with self.connect() as connection:
            # log.debug("Lets readers work while a writer writes")
            connection.execute("PRAGMA journal_mode = WAL")
            # log.debug("Reads how many migrations have run")
            done = int(connection.execute("PRAGMA user_version").fetchone()[0])
            # log.debug("Runs each migration not yet run")
            for number, script in enumerate(MIGRATIONS[done:], start=done + 1):
                # log.debug("Runs it and records its number in one transaction")
                connection.executescript(
                    f"BEGIN;\n{script}\nPRAGMA user_version = {int(number)};\nCOMMIT;"
                )
                # log.debug("Logs the migration")
                log_event(log, "store.migrated", version=number)
