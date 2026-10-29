########################################################################
#               backend/src/intake_agent/core/drafts.py                #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           Drafts, decisions and opening a matter: the      #
#                     approval gate, checked by role and record.       #
########################################################################
"""Drafts, decisions and opening a matter: the approval gate lives here.

A draft moves draft -> pending -> approved or rejected -> opened, and
only along those arrows. Opening is the one action with consequences,
so it is checked three times: the caller must hold the approver role,
an approval record must exist for the draft, and the database itself
refuses a new matter without one (core/store.py). The agent calls the
same `open` the approver's button does, with the requester's role
only, so its calls are always refused.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from typing import Literal

from kds.logs import get_logger, log_event

from intake_agent.core.models import (
    Actor,
    Approval,
    Decision,
    Draft,
    DraftRecord,
    DraftStatus,
    NewMatter,
)
from intake_agent.core.store import Store, utc_now

# Module constants
log = get_logger(__name__)
# log.debug("Names the role that may decide drafts and open matters")
APPROVER: Literal["approver"] = "approver"
# log.debug("Sets how new matter numbers are written")
NUMBER = "NM-{:05d}"
# log.debug("Sets the query that reads one draft with its decision and matter")
SELECT_ONE = """
    SELECT d.body, d.status, d.note AS submit_note,
           a.approver, a.approver_name, a.decision, a.note AS decision_note, a.decided_at,
           n.id AS matter_id, n.opened_by, n.opened_by_name, n.opened_at
    FROM drafts AS d
    LEFT JOIN approvals AS a ON a.draft_id = d.id
    LEFT JOIN new_matters AS n ON n.draft_id = d.id
    WHERE d.id = ?
"""
# log.debug("Sets the query that lists drafts, filtered by status and requester")
SELECT_MANY = """
    SELECT d.body, d.status, d.note AS submit_note,
           a.approver, a.approver_name, a.decision, a.note AS decision_note, a.decided_at,
           n.id AS matter_id, n.opened_by, n.opened_by_name, n.opened_at
    FROM drafts AS d
    LEFT JOIN approvals AS a ON a.draft_id = d.id
    LEFT JOIN new_matters AS n ON n.draft_id = d.id
    WHERE (:state IS NULL OR d.status = :state)
      AND (:requester IS NULL OR d.requester = :requester)
    ORDER BY d.created_at DESC, d.id
    LIMIT :limit
"""
# log.debug("Names the state of a draft waiting for a decision")
PENDING: Literal["pending"] = "pending"
# log.debug("Names the decision that lets a matter open")
APPROVED: Literal["approved"] = "approved"
# log.debug("Names the event a refused opening logs")
GATE_REFUSED = "gate.refused"
# log.debug("Names the column that holds the decision")
DECISION = "decision"
# log.debug("Names the column that holds the new matter's id")
MATTER_ID = "matter_id"
# log.debug("Sets the status change every action ends with")
SET_STATUS = "UPDATE drafts SET status = ? WHERE id = ?"


# log.debug("Defines the family of refusals a draft action can meet")
class DraftError(Exception):
    """A draft action was refused; the message says why."""


# log.debug("Defines the refusal for an unknown draft")
class DraftNotFoundError(DraftError, LookupError):
    """No draft has that id."""


# log.debug("Defines the refusal for an action the draft's state does not allow")
class DraftStateError(DraftError):
    """The draft is in the wrong state for this action."""


# log.debug("Defines the refusal for a caller who may not do this")
class GateError(DraftError, PermissionError):
    """The caller may not take this action on this draft."""


# log.debug("Defines the refusal for approving a flagged draft without a reason")
class ReasonRequiredError(DraftError, ValueError):
    """Approving over a flagged check needs a written reason."""


# log.debug("Defines the fingerprint an approval is bound to")
def fingerprint(draft: Draft) -> str:
    """Return the SHA-256 of the draft's JSON, which never changes."""
    # log.debug("Hashes the draft as saved")
    return hashlib.sha256(draft.model_dump_json().encode()).hexdigest()


# log.debug("Defines the book of drafts")
class DraftBook:
    """Saves drafts and moves them through their states."""

    # log.debug("Defines the constructor")
    def __init__(
        self, store: Store, *, min_reason_chars: int, clock: Callable[[], str] = utc_now
    ) -> None:
        """Keep drafts in `store`.

        Args:
            store: The database.
            min_reason_chars: The shortest reason for approving a draft
                whose checks found something.
            clock: Returns the time now; tests pass a fixed one.
        """
        # log.debug("Keeps the store")
        self.store = store
        # log.debug("Keeps the shortest reason allowed")
        self.min_reason_chars = min_reason_chars
        # log.debug("Keeps the clock")
        self.clock = clock

    # log.debug("Defines saving a new draft")
    def save(self, draft: Draft) -> None:
        """Save `draft` in the draft state; its text is then fixed."""
        # log.debug("Opens a transaction")
        with self.store.connect() as connection:
            # log.debug("Inserts the draft with its fingerprint")
            connection.execute(
                "INSERT INTO drafts (id, run_id, requester, created_at, body, sha256, status) "
                "VALUES (?, ?, ?, ?, ?, ?, 'draft')",
                (
                    draft.id,
                    draft.run_id,
                    draft.requester,
                    draft.created_at,
                    draft.model_dump_json(),
                    fingerprint(draft),
                ),
            )

    # log.debug("Defines reading one draft")
    def get(self, draft_id: str) -> DraftRecord:
        """Return the draft with its status, decision and matter.

        Raises:
            DraftNotFoundError: No draft has that id.
        """
        # log.debug("Opens a connection")
        with self.store.connect() as connection:
            # log.debug("Reads the draft")
            row = connection.execute(SELECT_ONE, (draft_id,)).fetchone()
        # log.debug("Refuses an unknown id")
        if row is None:
            # log.debug("Raises not found")
            raise DraftNotFoundError(f"no draft {draft_id}")
        # log.debug("Returns the record")
        return _record(row)

    # log.debug("Defines listing drafts, newest first")
    def find(
        self, *, status: DraftStatus | None = None, requester: str | None = None, limit: int = 50
    ) -> list[DraftRecord]:
        """Return drafts, newest first, by status and requester."""
        # log.debug("Opens a connection")
        with self.store.connect() as connection:
            # log.debug("Reads the drafts that pass both filters")
            rows = connection.execute(
                SELECT_MANY, {"state": status, "requester": requester, "limit": limit}
            ).fetchall()
        # log.debug("Returns them as records")
        return [_record(row) for row in rows]

    # log.debug("Defines sending a draft for approval")
    def submit(self, draft_id: str, *, run_id: str, note: str) -> DraftRecord:
        """Move a draft to pending, with a note; only its own run may.

        Raises:
            DraftNotFoundError: No draft has that id.
            GateError: The draft belongs to another run.
            DraftStateError: The draft is not in the draft state.
        """
        # log.debug("Reads the draft")
        record = self.get(draft_id)
        # log.debug("Refuses a draft another run made")
        if record.draft.run_id != run_id:
            # log.debug("Raises: a run may only submit its own draft")
            raise GateError(f"{draft_id} was made by another run")
        # log.debug("Refuses a draft already submitted")
        if record.status != "draft":
            # log.debug("Raises with its state")
            raise DraftStateError(f"{draft_id} is already {record.status}")
        # log.debug("Moves it to pending with the note for the approver")
        with self.store.connect() as connection:
            # log.debug("Sets the status and the note")
            connection.execute(
                "UPDATE drafts SET status = ?, note = ? WHERE id = ?", (PENDING, note, draft_id)
            )
        # log.debug("Logs the submission")
        log_event(log, "draft.submitted", draft_id=draft_id, run_id=run_id)
        # log.debug("Returns the draft as it now stands")
        return self.get(draft_id)

    # log.debug("Defines an approver's decision")
    def decide(
        self, draft_id: str, *, approver: Actor, decision: Decision, note: str
    ) -> DraftRecord:
        """Record an approver's decision on a pending draft.

        Raises:
            GateError: The caller is not an approver, or made the draft.
            DraftNotFoundError: No draft has that id.
            DraftStateError: The draft is not pending.
            ReasonRequiredError: Approving a flagged draft without a
                reason of the minimum length.
        """
        # log.debug("Refuses a caller without the approver role")
        if APPROVER not in approver.roles:
            # log.debug("Raises: only approvers decide")
            raise GateError("only an approver can decide a draft")
        # log.debug("Reads the draft")
        record = self.get(draft_id)
        # log.debug("Refuses a draft that is not waiting for a decision")
        if record.status != PENDING:
            # log.debug("Raises with its state")
            raise DraftStateError(f"{draft_id} is {record.status}, not pending")
        # log.debug("Refuses a requester deciding their own draft")
        if record.draft.requester == approver.user_id:
            # log.debug("Raises: two people must be involved")
            raise GateError("you made this draft; another approver must decide it")
        # log.debug("Asks for a reason before approving past a flagged check")
        if (
            decision == APPROVED
            and record.draft.recommendation != "clear"
            and len(note.strip()) < self.min_reason_chars
        ):
            # log.debug("Raises with the minimum length")
            msg = (
                f"the checks found a {record.draft.recommendation}; approving needs a reason "
                f"of at least {self.min_reason_chars} characters, such as a waiver on file"
            )
            # log.debug("Raises the refusal")
            raise ReasonRequiredError(msg)
        # log.debug("Writes the decision and the new status together")
        with self.store.connect() as connection:
            # log.debug("Inserts the decision, bound to the draft's fingerprint")
            connection.execute(
                "INSERT INTO approvals (draft_id, approver, approver_name, decision, note, "
                "draft_sha256, decided_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    draft_id,
                    approver.user_id,
                    approver.name,
                    decision,
                    note.strip(),
                    fingerprint(record.draft),
                    self.clock(),
                ),
            )
            # log.debug("Sets the status to the decision")
            connection.execute(SET_STATUS, (decision, draft_id))
        # log.debug("Logs the decision")
        log_event(log, "draft.decided", draft_id=draft_id, decision=decision)
        # log.debug("Returns the draft as it now stands")
        return self.get(draft_id)

    # log.debug("Defines the gate: opening a matter from an approved draft")
    def open(self, draft_id: str, *, actor: Actor) -> NewMatter:
        """Open a matter from an approved draft. The one gated action.

        Raises:
            GateError: The caller is not an approver, or no approval
                record exists for the draft.
            DraftNotFoundError: No draft has that id.
            DraftStateError: The matter is already open.
        """
        # log.debug("Refuses a caller without the approver role, the agent included")
        if APPROVER not in actor.roles:
            # log.debug("Logs the refusal")
            log_event(log, GATE_REFUSED, draft_id=draft_id, reason="role")
            # log.debug("Raises: only approvers open matters")
            raise GateError("only an approver can open a matter, after approving its draft")
        # log.debug("Reads the draft")
        record = self.get(draft_id)
        # log.debug("Refuses a matter already opened")
        if record.matter is not None:
            # log.debug("Raises with its number")
            raise DraftStateError(f"{draft_id} is already open as {record.matter.number}")
        # log.debug("Refuses a draft without an approval record")
        if record.approval is None or record.approval.decision != APPROVED:
            # log.debug("Logs the refusal")
            log_event(log, GATE_REFUSED, draft_id=draft_id, reason="no approval")
            # log.debug("Raises: approval first")
            raise GateError(f"{draft_id} has no approval record; an approver must approve it")
        # log.debug("Inserts the matter; the database checks the approval again")
        try:
            # log.debug("Opens a transaction for the matter and the status")
            with self.store.connect() as connection:
                # log.debug("Inserts the new matter")
                cursor = connection.execute(
                    "INSERT INTO new_matters (draft_id, opened_by, opened_by_name, opened_at) "
                    "VALUES (?, ?, ?, ?)",
                    (draft_id, actor.user_id, actor.name, self.clock()),
                )
                # log.debug("Marks the draft opened")
                connection.execute(SET_STATUS, ("opened", draft_id))
        except sqlite3.IntegrityError as error:
            # log.debug("Reports the database's refusal as the gate's")
            raise GateError(str(error)) from error
        # log.debug("Logs the opening")
        log_event(log, "matter.opened", draft_id=draft_id, matter_id=cursor.lastrowid)
        # log.debug("Reads the matter back")
        matter = self.get(draft_id).matter
        # log.debug("Treats a matter that cannot be read back as a fault")
        if matter is None:
            # log.debug("Raises, naming the draft")
            raise DraftStateError(f"the matter for {draft_id} was written but cannot be read")
        # log.debug("Returns the new matter")
        return matter


# log.debug("Defines how a row becomes a draft record")
def _record(row: sqlite3.Row) -> DraftRecord:
    """Return the draft, decision and matter a joined row holds."""
    # log.debug("Reads the decision, if one was made")
    approval = (
        Approval(
            approver=row["approver"],
            approver_name=row["approver_name"],
            decision=row[DECISION],
            note=row["decision_note"],
            decided_at=row["decided_at"],
        )
        if row[DECISION] is not None
        else None
    )
    # log.debug("Reads the matter, if one was opened")
    matter = (
        NewMatter(
            number=NUMBER.format(row[MATTER_ID]),
            opened_by=row["opened_by"],
            opened_by_name=row["opened_by_name"],
            opened_at=row["opened_at"],
        )
        if row[MATTER_ID] is not None
        else None
    )
    # log.debug("Returns the record")
    return DraftRecord(
        draft=Draft.model_validate_json(row["body"]),
        status=row["status"],
        note=row["submit_note"],
        approval=approval,
        matter=matter,
    )
