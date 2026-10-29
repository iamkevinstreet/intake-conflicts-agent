########################################################################
#                backend/src/intake_agent/core/seed.py                 #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Builds the made-up firm database once: the planted records from
data/samples/firm.json, then about 500 made-up names around them, as the
plan lays them out. A database that already holds clients is left alone,
so restarting the service never rebuilds it; the same seed always builds
the same database.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

# Third-party
from kds.args import required
from kds.logs import get_logger, log_event

# Local
from intake_agent.config import AppSettings
from intake_agent.core.plan import plan_firm
from intake_agent.core.planted import load_firm
from intake_agent.core.store import Store

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)


########################################################################
#                            Database seed                             #
########################################################################
# log.debug("Defines what seeding did")
@dataclass(frozen=True)
class SeedReport:
    """How many rows each table holds, and if seeding wrote them."""

    # log.debug("Holds the client count")
    clients: int
    # log.debug("Holds the matter count")
    matters: int
    # log.debug("Holds the adverse party count")
    adverse_parties: int
    # log.debug("Holds whether this call wrote them")
    created: bool


# log.debug("Defines seeding: build the database once, leave it alone after")
def seed(store: Store | None = None, settings: AppSettings | None = None) -> SeedReport:
    """Writes the planned rows into an empty database only.

    Args:
        store: The firm database to fill. Required.
        settings: The settings that name the planted-records file and
            give the seed and the counts. Required.

    Returns:
        The rows each table holds, and whether this call wrote them.
    """
    # log.debug("Takes the store, which the caller must give")
    store = required(store=store)
    # log.debug("Takes the settings, which the caller must give")
    settings = required(settings=settings)
    # log.debug("Opens one transaction for the whole seed")
    with store.connect() as connection:
        # log.debug("Counts what the database already holds")
        existing = _counts(connection)
        # log.debug("Leaves a database that already has clients alone")
        if existing[0]:
            # log.debug("Reports the existing counts")
            return SeedReport(*existing, created=False)
        # log.debug("Plans every row from the planted file and the seed")
        plan = plan_firm(load_firm(settings.data_firm), settings)
        # log.debug("Writes the clients; row ids follow plan positions")
        connection.executemany(
            "INSERT INTO clients (id, name, status) VALUES (?, ?, ?)",
            [(i + 1, name, status) for i, (name, status) in enumerate(plan.clients)],
        )
        # log.debug("Writes the matters")
        connection.executemany(
            "INSERT INTO matters (id, number, client_id, kind, status) VALUES (?, ?, ?, ?, ?)",
            [
                (i + 1, n, c + 1, kind, status)
                for i, (n, c, kind, status) in enumerate(plan.matters)
            ],
        )
        # log.debug("Writes the adverse parties")
        connection.executemany(
            "INSERT INTO adverse_parties (name, matter_id) VALUES (?, ?)",
            [(name, matter + 1) for name, matter in plan.adverse],
        )
        # log.debug("Reads back the counts")
        report = SeedReport(*_counts(connection), created=True)
    # log.debug("Logs what was written")
    log_event(log, "store.seeded", clients=report.clients, adverse=report.adverse_parties)
    # log.debug("Returns the report")
    return report


# log.debug("Defines the three counts")
def _counts(connection: sqlite3.Connection | None = None) -> tuple[int, int, int]:
    """Returns the client, matter and adverse party counts.

    Args:
        connection: An open connection to the firm database. Required.

    Returns:
        The number of clients, matters and adverse parties, in that
        order.
    """
    # log.debug("Takes the connection, which the caller must give")
    connection = required(connection=connection)
    # log.debug("Counts each table")
    return (
        int(connection.execute("SELECT COUNT(*) FROM clients").fetchone()[0]),
        int(connection.execute("SELECT COUNT(*) FROM matters").fetchone()[0]),
        int(connection.execute("SELECT COUNT(*) FROM adverse_parties").fetchone()[0]),
    )
