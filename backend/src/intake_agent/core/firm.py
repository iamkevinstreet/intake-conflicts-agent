########################################################################
#                backend/src/intake_agent/core/firm.py                 #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           Read-only access to the firm's clients and       #
#                     adverse parties, the only view the searches get. #
########################################################################
"""The firm's records the agent may read: clients and adverse parties.

The search tools see the firm only through `Directory`, a read-only
interface with two methods. The SQLite implementation is the only one
the service uses; the evaluation wraps it to make the database time
out, and tests replace it with a list.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from kds.logs import get_logger

from intake_agent.core.store import Store

# Module constants
log = get_logger(__name__)
# log.debug("Lists a client's standing with the firm")
ClientStatus = Literal["current", "former"]
# log.debug("Lists whether a matter is still being worked")
MatterStatus = Literal["open", "closed"]
# log.debug("Lists the fixed query that counts each table")
COUNTS = {
    "clients": "SELECT COUNT(*) FROM clients",
    "matters": "SELECT COUNT(*) FROM matters",
    "adverse_parties": "SELECT COUNT(*) FROM adverse_parties",
}


# log.debug("Defines one client of the firm")
@dataclass(frozen=True)
class ClientRecord:
    """A client, current or former."""

    # log.debug("Holds the row id")
    id: int
    # log.debug("Holds the name as the firm recorded it")
    name: str
    # log.debug("Holds whether the firm still acts for them")
    status: ClientStatus


# log.debug("Defines one party the firm has been against")
@dataclass(frozen=True)
class AdverseRecord:
    """A party on the other side of one of the firm's matters."""

    # log.debug("Holds the row id")
    id: int
    # log.debug("Holds the name as the firm recorded it")
    name: str
    # log.debug("Holds the number of the matter they were adverse in")
    matter: str
    # log.debug("Holds whether that matter is open or closed")
    matter_status: MatterStatus
    # log.debug("Holds the client the firm acted for in that matter")
    matter_client: str


# log.debug("Defines what the search tools may read, and nothing more")
class Directory(Protocol):
    """Read-only access to the names a conflicts search compares."""

    # log.debug("Defines the read of every client")
    def clients(self) -> list[ClientRecord]:
        """Return every client, current and former."""

    # log.debug("Defines the read of every adverse party")
    def adverse_parties(self) -> list[AdverseRecord]:
        """Return every party the firm has been adverse to."""


# log.debug("Defines the directory backed by the firm database")
class SqliteDirectory:
    """Reads clients and adverse parties from the store."""

    # log.debug("Defines the constructor")
    def __init__(self, store: Store) -> None:
        """Read from `store`."""
        # log.debug("Keeps the store")
        self.store = store

    # log.debug("Defines the read of every client")
    def clients(self) -> list[ClientRecord]:
        """Return every client, in id order."""
        # log.debug("Opens a connection for the read")
        with self.store.connect() as connection:
            # log.debug("Reads the clients")
            rows = connection.execute("SELECT id, name, status FROM clients ORDER BY id")
            # log.debug("Returns them as records; the columns are named as the fields")
            return [ClientRecord(**dict(row)) for row in rows]

    # log.debug("Defines the read of every adverse party, with its matter")
    def adverse_parties(self) -> list[AdverseRecord]:
        """Return every adverse party with its matter and client."""
        # log.debug("Opens a connection for the read")
        with self.store.connect() as connection:
            # log.debug("Reads each adverse party joined to its matter and client")
            rows = connection.execute(
                """
                SELECT a.id, a.name, m.number AS matter, m.status AS matter_status,
                       c.name AS matter_client
                FROM adverse_parties AS a
                JOIN matters AS m ON m.id = a.matter_id
                JOIN clients AS c ON c.id = m.client_id
                ORDER BY a.id
                """
            )
            # log.debug("Returns them as records; the columns are named as the fields")
            return [AdverseRecord(**dict(row)) for row in rows]

    # log.debug("Defines the size report the health check shows")
    def counts(self) -> dict[str, int]:
        """Return the client, matter and adverse party counts."""
        # log.debug("Opens a connection for the counts")
        with self.store.connect() as connection:
            # log.debug("Returns one count per table")
            return {
                table: int(connection.execute(query).fetchone()[0])
                for table, query in COUNTS.items()
            }
