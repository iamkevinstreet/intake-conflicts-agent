########################################################################
#                backend/src/intake_agent/core/audit.py                #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Writes and reads the audit log: one record per run, model call and tool
call, the email only as a hash. Each tool call is written with its
arguments (contact details and ID numbers redacted; party names kept,
since showing what was searched is the point), whether it worked, how
long it took, and the SHA-256 of what came back. Each model call is
written with its tokens, cost and time. The intake email itself is never
written here, only its hash and length, which tie a run to the draft an
approver sees. The database refuses any edit to a finished record
(core/store.py).
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from typing import Any

# Third-party
from kds.args import required
from kds.llm import Completion
from kds.logs import get_logger, log_event, redact_obj

# Local
from intake_agent.core.models import Actor
from intake_agent.core.records import (
    ModelCallRecord,
    RunDetail,
    RunRecord,
    RunTotals,
    ToolCallRecord,
)
from intake_agent.core.store import Store, utc_now

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)

########################################################################
#                           Local constants                            #
########################################################################
# log.debug("Names the column that holds a tool call's arguments")
ARGUMENTS = "arguments"
# log.debug("Sets the query for one run")
RUN_ONE = "SELECT * FROM runs WHERE id = ?"
# log.debug("Sets the query for recent runs, everyone's or one requester's")
RUN_MANY = (
    "SELECT * FROM runs WHERE (:requester IS NULL OR requester = :requester) "
    "ORDER BY started_at DESC, id LIMIT :limit"
)


########################################################################
#                              Audit log                               #
########################################################################
# log.debug("Defines the fingerprint of any JSON value")
def digest(value: Any = None) -> str:
    """Returns the SHA-256 of a value's canonical JSON.

    Args:
        value: Any value JSON can hold; anything else is written as
            text, and None is hashed as JSON's null.

    Returns:
        The hash in hex, the same for equal values whatever the order
        of their keys.
    """
    # log.debug("Hashes the value with sorted keys, so equal values match")
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


# log.debug("Defines the log of runs")
class RunLog:
    """Writes and reads the audit records."""

    # log.debug("Defines the constructor")
    def __init__(self, store: Store | None = None, clock: Callable[[], str] = utc_now) -> None:
        """Writes to `store`; `clock` gives the time (tests fix it).

        Args:
            store: The firm database the records go in. Required.
            clock: Gives the time each record is stamped with.
        """
        # log.debug("Takes the store, which the caller must give")
        store = required(store=store)
        # log.debug("Keeps the store")
        self.store = store
        # log.debug("Keeps the clock")
        self.clock = clock

    # log.debug("Defines the start of a run")
    def start(
        self,
        run_id: str | None = None,
        *,
        actor: Actor | None = None,
        email: str | None = None,
        model: str | None = None,
    ) -> None:
        """Records that a run began, for whom, on which email.

        Args:
            run_id: The new run's id. Required.
            actor: The requester the run works for. Required.
            email: The intake email; only its hash and length are
                written. Required.
            model: The model that plays the agent. Required.
        """
        # log.debug("Takes the run id, which the caller must give")
        run_id = required(run_id=run_id)
        # log.debug("Takes the requester, which the caller must give")
        actor = required(actor=actor)
        # log.debug("Takes the email, which the caller must give")
        email = required(email=email)
        # log.debug("Takes the model, which the caller must give")
        model = required(model=model)
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
    def model_call(
        self,
        run_id: str | None = None,
        step: int | None = None,
        completion: Completion | None = None,
    ) -> None:
        """Records a model call's tokens, cost, time and stop reason.

        Args:
            run_id: The run the call belongs to. Required.
            step: The call's number in the run, from 1. Required.
            completion: The model's answer, with its usage, cost and
                time. Required.
        """
        # log.debug("Takes the run id, which the caller must give")
        run_id = required(run_id=run_id)
        # log.debug("Takes the step, which the caller must give")
        step = required(step=step)
        # log.debug("Takes the model's answer, which the caller must give")
        completion = required(completion=completion)
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
        run_id: str | None = None,
        *,
        seq: int | None = None,
        step: int | None = None,
        tool: str | None = None,
        arguments: dict[str, Any] | None = None,
        ok: bool | None = None,
        error: str | None = None,
        result: Any = None,
        ms: int | None = None,
    ) -> None:
        """Records a tool call: arguments redacted, result hashed.

        Args:
            run_id: The run the call belongs to. Required.
            seq: The call's place in the run, from 1. Required.
            step: The model call that asked for it. Required.
            tool: The tool's name. Required.
            arguments: The arguments the model gave, redacted before
                they are written. Required.
            ok: Whether the tool did what was asked. Required.
            error: The refusal or error; empty when it worked.
                Required.
            result: What the tool handed back; only its hash is
                written, and None is hashed as JSON's null.
            ms: How long the call took, in milliseconds. Required.
        """
        # log.debug("Takes the run id, which the caller must give")
        run_id = required(run_id=run_id)
        # log.debug("Takes the call's place in the run, which the caller must give")
        seq = required(seq=seq)
        # log.debug("Takes the step, which the caller must give")
        step = required(step=step)
        # log.debug("Takes the tool's name, which the caller must give")
        tool = required(tool=tool)
        # log.debug("Takes the arguments, which the caller must give")
        arguments = required(arguments=arguments)
        # log.debug("Takes whether the tool worked, which the caller must give")
        ok = required(ok=ok)
        # log.debug("Takes the error, which the caller must give")
        error = required(error=error)
        # log.debug("Takes the time taken, which the caller must give")
        ms = required(ms=ms)
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
    def finish(self, run_id: str | None = None, totals: RunTotals | None = None) -> RunRecord:
        """Records how the run ended; after this the record is fixed.

        Args:
            run_id: The run that ended. Required.
            totals: How it ended and what it used. Required.

        Returns:
            The finished record, read back from the database.

        Raises:
            LookupError: The run was written but cannot be read back.
        """
        # log.debug("Takes the run id, which the caller must give")
        run_id = required(run_id=run_id)
        # log.debug("Takes the totals, which the caller must give")
        totals = required(totals=totals)
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
    def run(self, run_id: str | None = None) -> RunRecord | None:
        """Returns the run, or None if there is none with that id.

        Args:
            run_id: The run's id. Required.

        Returns:
            The run's record, or None when no run has the id.
        """
        # log.debug("Takes the run id, which the caller must give")
        run_id = required(run_id=run_id)
        # log.debug("Reads it")
        with self.store.connect() as connection:
            # log.debug("Fetches the row")
            row = connection.execute(RUN_ONE, (run_id,)).fetchone()
        # log.debug("Returns it as a record, or None")
        return None if row is None else RunRecord.model_validate(dict(row))

    # log.debug("Defines listing runs, newest first")
    def runs(self, *, requester: str | None = None, limit: int = 50) -> list[RunRecord]:
        """Returns recent runs: everyone's, or one requester's.

        Args:
            requester: The requester whose runs to list; None lists
                everyone's.
            limit: The most runs to return.

        Returns:
            The runs, newest first.
        """
        # log.debug("Reads them")
        with self.store.connect() as connection:
            # log.debug("Fetches the rows")
            rows = connection.execute(
                RUN_MANY, {"requester": requester, "limit": limit}
            ).fetchall()
        # log.debug("Returns them as records")
        return [RunRecord.model_validate(dict(row)) for row in rows]

    # log.debug("Defines reading a run with every call it made")
    def detail(self, run_id: str | None = None) -> RunDetail | None:
        """Returns the run and its calls in order, or None.

        Args:
            run_id: The run's id. Required.

        Returns:
            The run with its model calls and tool calls in the order
            they were made, or None when no run has the id.
        """
        # log.debug("Takes the run id, which the caller must give")
        run_id = required(run_id=run_id)
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
def _tool_call(row: sqlite3.Row | None = None) -> ToolCallRecord:
    """Returns the record, with its arguments parsed back from JSON.

    Args:
        row: A row of the tool_calls table. Required.

    Returns:
        The tool call's record, its arguments a dictionary again.
    """
    # log.debug("Takes the row, which the caller must give")
    row = required(row=row)
    # log.debug("Copies the row")
    data = dict(row)
    # log.debug("Parses the arguments")
    data[ARGUMENTS] = json.loads(data[ARGUMENTS])
    # log.debug("Returns the record")
    return ToolCallRecord.model_validate(data)
