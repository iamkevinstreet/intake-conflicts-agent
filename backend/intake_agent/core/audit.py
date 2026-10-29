########################################################################
#                  backend/intake_agent/core/audit.py                  #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           The audit log: one record per run, model call    #
#                     and tool call; the email only as a hash.         #
########################################################################
"""The audit log: one record per run, one per model call and tool call.

Each tool call is written with its arguments (contact details and ID
numbers redacted; party names kept, since showing what was searched is
the point), whether it worked, how long it took, and the SHA-256 of
what came back. Each model call is written with its tokens, cost and
time. The intake email itself is never written here, only its hash
and length, which tie a run to the draft an approver sees. The
database refuses any edit to a finished record (core/store.py).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from typing import Any

from kds.llm import Completion
from kds.logs import get_logger, log_event, redact_obj
from pydantic import BaseModel, ConfigDict

from intake_agent.core.models import Actor, Outcome
from intake_agent.core.store import Store, utc_now

# Module constants
log = get_logger(__name__)
# log.debug("Sets the settings shared by the audit records")
FROZEN = ConfigDict(frozen=True)
# log.debug("Names the column that holds a tool call's arguments")
ARGUMENTS = "arguments"
# log.debug("Sets the query for one run")
RUN_ONE = "SELECT * FROM runs WHERE id = ?"
# log.debug("Sets the query for recent runs, everyone's or one requester's")
RUN_MANY = (
    "SELECT * FROM runs WHERE (:requester IS NULL OR requester = :requester) "
    "ORDER BY started_at DESC, id LIMIT :limit"
)


# log.debug("Defines the record of one run")
class RunRecord(BaseModel):
    """A run: who, when, which email (hashed), outcome and cost."""

    # log.debug("Freezes the record once built")
    model_config = FROZEN

    # log.debug("Holds the run id")
    id: str
    # log.debug("Holds the requester's id")
    requester: str
    # log.debug("Holds the requester's name")
    requester_name: str
    # log.debug("Holds when it started, UTC")
    started_at: str
    # log.debug("Holds when it finished, UTC; empty while running")
    finished_at: str | None
    # log.debug("Holds the SHA-256 of the intake email")
    email_sha256: str
    # log.debug("Holds the email's length in characters")
    email_chars: int
    # log.debug("Holds the model the run used")
    model: str
    # log.debug("Holds how it ended")
    outcome: Outcome
    # log.debug("Holds why, in a sentence")
    reason: str
    # log.debug("Holds the draft it made, if any")
    draft_id: str | None
    # log.debug("Holds how many model calls it made")
    steps: int
    # log.debug("Holds how many tool calls it made")
    tool_calls: int
    # log.debug("Holds the tokens the model read")
    input_tokens: int
    # log.debug("Holds the tokens the model wrote")
    output_tokens: int
    # log.debug("Holds the cost in US dollars; empty for an unpriced model")
    cost_usd: float | None
    # log.debug("Holds the run's wall-clock time in milliseconds")
    ms: int


# log.debug("Defines the record of one model call")
class ModelCallRecord(BaseModel):
    """One call to the model: tokens, cost, time, why it stopped."""

    # log.debug("Freezes the record once built")
    model_config = FROZEN

    # log.debug("Holds the step number, from 1")
    step: int
    # log.debug("Holds the tokens read")
    input_tokens: int
    # log.debug("Holds the tokens written")
    output_tokens: int
    # log.debug("Holds the cost")
    cost_usd: float | None
    # log.debug("Holds the time taken")
    ms: int
    # log.debug("Holds why the model stopped")
    stop_reason: str


# log.debug("Defines the record of one tool call")
class ToolCallRecord(BaseModel):
    """One tool call: what was asked, if it worked, what came back."""

    # log.debug("Freezes the record once built")
    model_config = FROZEN

    # log.debug("Holds the call's place in the run, from 1")
    seq: int
    # log.debug("Holds the model call that asked for it")
    step: int
    # log.debug("Holds the tool's name")
    tool: str
    # log.debug("Holds the arguments, redacted")
    arguments: dict[str, Any]
    # log.debug("Holds whether it worked")
    ok: bool
    # log.debug("Holds the refusal or error, if it did not")
    error: str
    # log.debug("Holds the SHA-256 of what came back")
    result_sha256: str
    # log.debug("Holds the time taken")
    ms: int
    # log.debug("Holds when, UTC")
    at: str


# log.debug("Defines a run with all its calls")
class RunDetail(BaseModel):
    """A run and every call it made, in order."""

    # log.debug("Freezes the record once built")
    model_config = FROZEN

    # log.debug("Holds the run")
    run: RunRecord
    # log.debug("Holds its model calls")
    model_calls: list[ModelCallRecord]
    # log.debug("Holds its tool calls")
    tool_calls: list[ToolCallRecord]


# log.debug("Defines the totals a run finishes with")
class RunTotals(BaseModel):
    """How a run ended and what it used."""

    # log.debug("Freezes the record once built")
    model_config = FROZEN

    # log.debug("Holds how it ended")
    outcome: Outcome
    # log.debug("Holds why")
    reason: str
    # log.debug("Holds the draft it made")
    draft_id: str | None
    # log.debug("Holds the model calls")
    steps: int
    # log.debug("Holds the tool calls")
    tool_calls: int
    # log.debug("Holds the tokens read")
    input_tokens: int
    # log.debug("Holds the tokens written")
    output_tokens: int
    # log.debug("Holds the cost")
    cost_usd: float | None
    # log.debug("Holds the time")
    ms: int


# log.debug("Defines the fingerprint of any JSON value")
def digest(value: Any) -> str:
    """Return the SHA-256 of a value's canonical JSON."""
    # log.debug("Hashes the value with sorted keys, so equal values match")
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


# log.debug("Defines the log of runs")
class RunLog:
    """Writes and reads the audit records."""

    # log.debug("Defines the constructor")
    def __init__(self, store: Store, clock: Callable[[], str] = utc_now) -> None:
        """Write to `store`; `clock` gives the time (tests fix it)."""
        # log.debug("Keeps the store")
        self.store = store
        # log.debug("Keeps the clock")
        self.clock = clock

    # log.debug("Defines the start of a run")
    def start(self, run_id: str, *, actor: Actor, email: str, model: str) -> None:
        """Record that a run began, for whom, on which email."""
        # log.debug("Inserts the run as running")
        with self.store.connect() as connection:
            # log.debug("Writes the record")
            connection.execute(
                "INSERT INTO runs (id, requester, requester_name, started_at, email_sha256, "
                "email_chars, model) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    actor.user_id,
                    actor.name,
                    self.clock(),
                    hashlib.sha256(email.encode()).hexdigest(),
                    len(email),
                    model,
                ),
            )

    # log.debug("Defines the record of a model call")
    def model_call(self, run_id: str, step: int, completion: Completion) -> None:
        """Record a model call's tokens, cost, time and stop reason."""
        # log.debug("Inserts the call")
        with self.store.connect() as connection:
            # log.debug("Writes the record")
            connection.execute(
                "INSERT INTO model_calls (run_id, step, input_tokens, output_tokens, cost_usd, "
                "ms, stop_reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    step,
                    completion.usage.input_tokens,
                    completion.usage.output_tokens,
                    completion.cost_usd,
                    completion.latency_ms,
                    completion.stop_reason or "",
                ),
            )

    # log.debug("Defines the record of a tool call")
    def tool_call(  # noqa: PLR0913 - every field is named at the call
        self,
        run_id: str,
        *,
        seq: int,
        step: int,
        tool: str,
        arguments: dict[str, Any],
        ok: bool,
        error: str,
        result: Any,
        ms: int,
    ) -> None:
        """Record a tool call: arguments redacted, result hashed."""
        # log.debug("Inserts the call")
        with self.store.connect() as connection:
            # log.debug("Writes the record")
            connection.execute(
                "INSERT INTO tool_calls (run_id, seq, step, tool, arguments, ok, error, "
                "result_sha256, ms, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    seq,
                    step,
                    tool,
                    json.dumps(redact_obj(arguments), sort_keys=True),
                    int(ok),
                    error,
                    digest(result),
                    ms,
                    self.clock(),
                ),
            )

    # log.debug("Defines the end of a run")
    def finish(self, run_id: str, totals: RunTotals) -> RunRecord:
        """Record how the run ended; after this the record is fixed."""
        # log.debug("Updates the run once; the database refuses a second update")
        with self.store.connect() as connection:
            # log.debug("Writes the totals")
            connection.execute(
                "UPDATE runs SET outcome = ?, reason = ?, draft_id = ?, steps = ?, "
                "tool_calls = ?, input_tokens = ?, output_tokens = ?, cost_usd = ?, ms = ?, "
                "finished_at = ? WHERE id = ?",
                (
                    totals.outcome,
                    totals.reason,
                    totals.draft_id,
                    totals.steps,
                    totals.tool_calls,
                    totals.input_tokens,
                    totals.output_tokens,
                    totals.cost_usd,
                    totals.ms,
                    self.clock(),
                    run_id,
                ),
            )
        # log.debug("Logs the run as one line, with no email text")
        log_event(log, "run.done", run_id=run_id, **totals.model_dump(exclude={"reason"}))
        # log.debug("Reads the finished record back")
        record = self.run(run_id)
        # log.debug("Treats a run that cannot be read back as a fault")
        if record is None:
            # log.debug("Raises, naming the run")
            raise LookupError(f"run {run_id} was written but cannot be read")
        # log.debug("Returns the finished record")
        return record

    # log.debug("Defines reading one run")
    def run(self, run_id: str) -> RunRecord | None:
        """Return the run, or None if there is none with that id."""
        # log.debug("Reads it")
        with self.store.connect() as connection:
            # log.debug("Fetches the row")
            row = connection.execute(RUN_ONE, (run_id,)).fetchone()
        # log.debug("Returns it as a record, or None")
        return None if row is None else RunRecord.model_validate(dict(row))

    # log.debug("Defines listing runs, newest first")
    def runs(self, *, requester: str | None = None, limit: int = 50) -> list[RunRecord]:
        """Return recent runs: everyone's, or one requester's."""
        # log.debug("Reads them")
        with self.store.connect() as connection:
            # log.debug("Fetches the rows")
            rows = connection.execute(
                RUN_MANY, {"requester": requester, "limit": limit}
            ).fetchall()
        # log.debug("Returns them as records")
        return [RunRecord.model_validate(dict(row)) for row in rows]

    # log.debug("Defines reading a run with every call it made")
    def detail(self, run_id: str) -> RunDetail | None:
        """Return the run and its calls in order, or None."""
        # log.debug("Reads the run")
        run = self.run(run_id)
        # log.debug("Returns None for an unknown run")
        if run is None:
            # log.debug("Returns None")
            return None
        # log.debug("Reads its calls")
        with self.store.connect() as connection:
            # log.debug("Fetches the model calls in order")
            steps = connection.execute(
                "SELECT * FROM model_calls WHERE run_id = ? ORDER BY step", (run_id,)
            ).fetchall()
            # log.debug("Fetches the tool calls in order")
            calls = connection.execute(
                "SELECT * FROM tool_calls WHERE run_id = ? ORDER BY seq", (run_id,)
            ).fetchall()
        # log.debug("Returns the run with its calls")
        return RunDetail(
            run=run,
            model_calls=[ModelCallRecord.model_validate(dict(row)) for row in steps],
            tool_calls=[_tool_call(row) for row in calls],
        )


# log.debug("Defines how a tool-call row becomes a record")
def _tool_call(row: sqlite3.Row) -> ToolCallRecord:
    """Return the record, with its arguments parsed back from JSON."""
    # log.debug("Copies the row")
    data = dict(row)
    # log.debug("Parses the arguments")
    data[ARGUMENTS] = json.loads(data[ARGUMENTS])
    # log.debug("Returns the record")
    return ToolCallRecord.model_validate(data)
