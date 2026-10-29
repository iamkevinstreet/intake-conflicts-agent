########################################################################
#                     backend/tests/test_store.py                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Tests the database rules: migrations run once, and the triggers that
hold the gate and the audit.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

import sqlite3
from pathlib import Path

# Third-party
import pytest
from kds.args import required
from kds.logs import get_logger

# Local
from intake_agent.core.store import MIGRATIONS, Store

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)

########################################################################
#                           Local constants                            #
########################################################################
# log.debug("Sets the insert of a draft row")
INSERT_DRAFT = (
    "INSERT INTO drafts (id, run_id, requester, created_at, body, sha256, status) "
    "VALUES (?, 'R-0000000000', 'dev:avery', '2026-10-29T00:00:00+00:00', '{}', 'abc', ?)"
)
# log.debug("Sets the insert of an approval row")
INSERT_APPROVAL = (
    "INSERT INTO approvals (draft_id, approver, approver_name, decision, note, draft_sha256, "
    "decided_at) VALUES (?, ?, 'Jordan', ?, '', ?, '2026-10-29T00:00:00+00:00')"
)


########################################################################
#                         Database rule tests                          #
########################################################################
# log.debug("Defines a store with one draft in a given state")
def _store_with_draft(tmp_path: Path | None = None, status: str | None = None) -> Store:
    """Returns a fresh store holding draft D-1 in `status`.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
            Required.
        status: The draft's status. Required.

    Returns:
        A fresh store holding draft D-1 in that status.
    """
    # log.debug("Takes the temporary folder, which the caller must give")
    tmp_path = required(tmp_path=tmp_path)
    # log.debug("Takes the status, which the caller must give")
    status = required(status=status)
    # log.debug("Opens the store")
    store = Store(tmp_path / "t.sqlite", timeout_s=1)
    # log.debug("Writes the draft")
    with store.connect() as connection:
        # log.debug("Inserts it")
        connection.execute(INSERT_DRAFT, ("D-1", status))
    # log.debug("Returns the store")
    return store


# log.debug("Defines the migration test")
def test_migrations_run_once(tmp_path: Path) -> None:
    """Reopening a migrated database changes nothing.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
    """
    # log.debug("Opens the store twice")
    Store(tmp_path / "t.sqlite", timeout_s=1)
    # log.debug("Opens it again")
    store = Store(tmp_path / "t.sqlite", timeout_s=1)
    # log.debug("Reads the recorded version")
    with store.connect() as connection:
        # log.debug("Fetches it")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    # log.debug("Checks it equals the number of migrations")
    assert version == len(MIGRATIONS)


# log.debug("Defines the database's own gate test")
def test_no_matter_without_an_approval_record(tmp_path: Path) -> None:
    """Even a direct insert, past the Python, is refused.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
    """
    # log.debug("Builds a store with an approved-status draft but no approval row")
    store = _store_with_draft(tmp_path, "approved")
    # log.debug("Expects the trigger to refuse the matter")
    with pytest.raises(sqlite3.IntegrityError, match="no approval record"):
        # log.debug("Tries the insert")
        with store.connect() as connection:
            # log.debug("Inserts the matter")
            connection.execute(
                "INSERT INTO new_matters (draft_id, opened_by, opened_by_name, opened_at) "
                "VALUES ('D-1', 'x', 'x', 'now')"
            )


# log.debug("Defines the rejected-draft gate test")
def test_no_matter_after_a_rejection(tmp_path: Path) -> None:
    """A rejection record is not an approval.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
    """
    # log.debug("Builds a store with a pending draft")
    store = _store_with_draft(tmp_path, "pending")
    # log.debug("Records a rejection, then tries to open")
    with pytest.raises(sqlite3.IntegrityError, match="no approval record"):
        # log.debug("Writes both in one transaction")
        with store.connect() as connection:
            # log.debug("Records a rejection")
            connection.execute(INSERT_APPROVAL, ("D-1", "dev:jordan", "rejected", "abc"))
            # log.debug("Tries to open")
            connection.execute(
                "INSERT INTO new_matters (draft_id, opened_by, opened_by_name, opened_at) "
                "VALUES ('D-1', 'x', 'x', 'now')"
            )


# log.debug("Defines the approval rules the schema enforces")
@pytest.mark.parametrize(
    ("status", "approver", "sha", "message"),
    [
        ("draft", "dev:jordan", "abc", "only a draft awaiting approval"),
        ("pending", "dev:avery", "abc", "cannot decide their own draft"),
        ("pending", "dev:jordan", "other", "does not match the saved draft"),
    ],
)
def test_approval_rules(
    tmp_path: Path, status: str, approver: str, sha: str, message: str
) -> None:
    """Pending only, not by the requester, bound to the hash.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
        status: The draft's status when the approval is tried.
        approver: Who approves.
        sha: The draft hash the approval is bound to.
        message: The refusal the trigger gives.
    """
    # log.debug("Builds the store")
    store = _store_with_draft(tmp_path, status)
    # log.debug("Expects the refusal")
    with pytest.raises(sqlite3.IntegrityError, match=message):
        # log.debug("Tries the approval")
        with store.connect() as connection:
            # log.debug("Inserts it")
            connection.execute(INSERT_APPROVAL, ("D-1", approver, "approved", sha))


# log.debug("Defines the records that can never change")
@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE drafts SET body = '{\"x\": 1}' WHERE id = 'D-1'",
        "DELETE FROM drafts WHERE id = 'D-1'",
    ],
)
def test_a_saved_draft_cannot_be_rewritten_or_deleted(tmp_path: Path, statement: str) -> None:
    """The text an approver approves is the text that was saved.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
        statement: A statement that would change or delete the saved
            draft.
    """
    # log.debug("Builds the store")
    store = _store_with_draft(tmp_path, "pending")
    # log.debug("Expects the refusal")
    with pytest.raises(sqlite3.IntegrityError):
        # log.debug("Tries the change")
        with store.connect() as connection:
            # log.debug("Runs it")
            connection.execute(statement)


# log.debug("Defines the audit-record tests")
def test_audit_records_are_append_only(tmp_path: Path) -> None:
    """A finished run cannot change; tool calls cannot change at all.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
    """
    # log.debug("Opens a store")
    store = Store(tmp_path / "t.sqlite", timeout_s=1)
    # log.debug("Writes a finished run and one tool call")
    with store.connect() as connection:
        # log.debug("Inserts the run")
        connection.execute(
            "INSERT INTO runs (id, requester, requester_name, started_at, email_sha256, "
            "email_chars, model, outcome) VALUES ('R-1', 'u', 'U', 't', 'h', 1, 'm', 'failed')"
        )
        # log.debug("Inserts the tool call")
        connection.execute(
            "INSERT INTO tool_calls (run_id, seq, step, tool, arguments, ok, error, "
            "result_sha256, ms, at) VALUES ('R-1', 1, 1, 't', '{}', 1, '', 'h', 1, 't')"
        )
    # log.debug("Tries each forbidden change")
    for statement in (
        "UPDATE runs SET outcome = 'submitted' WHERE id = 'R-1'",
        "DELETE FROM runs WHERE id = 'R-1'",
        "UPDATE tool_calls SET ok = 0",
        "DELETE FROM tool_calls",
    ):
        # log.debug("Expects the refusal")
        with pytest.raises(sqlite3.IntegrityError), store.connect() as connection:
            # log.debug("Runs the change")
            connection.execute(statement)
