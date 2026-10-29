########################################################################
#                backend/src/intake_agent/core/seed.py                 #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           Builds the made-up firm database: planted        #
#                     records, then about 500 names around them.       #
########################################################################
"""Builds the made-up firm database the agent searches.

It starts from the records planted in data/samples/firm.json, which
the evaluation's scenarios are written around, then adds made-up
clients, matters and adverse parties until the counts in settings are
reached. A share of the made-up adverse parties are near duplicates of
made-up clients ("Westbrook Cosulting" beside "Westbrook Consulting
LLP"), the mess real intake data has. Every made-up name is kept below
the possible-match score against every planted and reserved name, so
no generated record can change what a scenario should find. The same
seed always builds the same database.
"""

from __future__ import annotations

import json
import random
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

from kds.logs import get_logger, log_event
from kds.synthetic import NameGen, near_duplicates
from pydantic import BaseModel, Field, model_validator

from intake_agent.config import AppSettings
from intake_agent.core.firm import ClientStatus, MatterStatus
from intake_agent.core.names import normalize, score_plain
from intake_agent.core.store import Store

# Module constants
log = get_logger(__name__)
# log.debug("Lists the kinds of matter the made-up records are")
MATTER_KINDS = (
    "wage and hour claim",
    "non-compete enforcement",
    "wrongful termination claim",
    "discrimination charge",
    "harassment investigation",
    "trade secret dispute",
    "contractor classification review",
    "OSHA citation",
    "executive separation agreement",
    "workforce reduction",
    "leave and accommodation dispute",
    "union organizing campaign",
)
# log.debug("Sets the share of made-up clients that are companies")
CLIENT_COMPANY_SHARE = 0.7
# log.debug("Sets the share of made-up adverse parties that are companies")
ADVERSE_COMPANY_SHARE = 0.5
# log.debug("Sets the first number given to a made-up matter")
FIRST_MATTER = 2001
# log.debug("Sets how many tries per wanted name before giving up")
TRIES_PER_NAME = 50
# log.debug("Matches a matter number")
MATTER_NUMBER = r"^M-\d{4}$"


# log.debug("Defines a planted client")
class PlantedClient(BaseModel):
    """A client the scenarios are written around."""

    # log.debug("Holds the name")
    name: str = Field(min_length=1)
    # log.debug("Holds current or former")
    status: ClientStatus


# log.debug("Defines a planted matter")
class PlantedMatter(BaseModel):
    """A matter the scenarios are written around, with its parties."""

    # log.debug("Holds the matter number")
    number: str = Field(pattern=MATTER_NUMBER)
    # log.debug("Holds the client's name, one of the planted clients")
    client: str
    # log.debug("Holds the kind of matter")
    kind: str
    # log.debug("Holds open or closed")
    status: MatterStatus
    # log.debug("Holds the parties the firm is against in it")
    adverse: list[str]


# log.debug("Defines the planted-records file")
class FirmFile(BaseModel):
    """data/samples/firm.json: planted records and reserved names."""

    # log.debug("Holds the file's own description")
    about: str
    # log.debug("Holds the planted clients")
    clients: list[PlantedClient]
    # log.debug("Holds the planted matters")
    matters: list[PlantedMatter]
    # log.debug("Holds names the scenarios use for parties the firm never met")
    reserved: list[str]

    # log.debug("Defines the check that every matter's client is planted")
    @model_validator(mode="after")
    def _clients_exist(self) -> Self:
        """Refuse a matter whose client is not in the clients list."""
        # log.debug("Collects the planted client names")
        names = {client.name for client in self.clients}
        # log.debug("Finds matters whose client is missing")
        missing = [m.number for m in self.matters if m.client not in names]
        # log.debug("Refuses the file when any are missing")
        if missing:
            # log.debug("Raises, naming the matters")
            msg = f"matters with an unknown client: {', '.join(missing)}"
            # log.debug("Raises the refusal")
            raise ValueError(msg)
        # log.debug("Returns the file")
        return self

    # log.debug("Defines every name the generator must keep clear of")
    def protected(self) -> list[str]:
        """Return every planted and reserved name."""
        # log.debug("Collects clients, adverse parties and reserved names")
        return [
            *(client.name for client in self.clients),
            *(name for matter in self.matters for name in matter.adverse),
            *self.reserved,
        ]


# log.debug("Defines the rows the database will hold")
@dataclass
class Plan:
    """Clients, matters and adverse parties, ready to insert."""

    # log.debug("Holds each client: name and status")
    clients: list[tuple[str, str]] = field(default_factory=list)
    # log.debug("Holds each matter: number, client position, kind, status")
    matters: list[tuple[str, int, str, str]] = field(default_factory=list)
    # log.debug("Holds each adverse party: name and matter position")
    adverse: list[tuple[str, int]] = field(default_factory=list)
    # log.debug("Holds the positions of made-up clients that are companies")
    companies: list[int] = field(default_factory=list)


# log.debug("Defines the check that a made-up name stays clear of the protected ones")
@dataclass
class _Guard:
    """Accepts a name only if new and far from every protected one."""

    # log.debug("Holds the protected names in plain form")
    protected: list[str]
    # log.debug("Holds the score a made-up name must stay below")
    ceiling: int
    # log.debug("Holds the plain forms already used")
    taken: set[str] = field(default_factory=set)

    # log.debug("Defines the check")
    def accept(self, name: str, *, unique: bool) -> bool:
        """Return True, and remember the name, when it may be used."""
        # log.debug("Puts the name in plain form")
        plain = normalize(name)
        # log.debug("Refuses a repeat when names must be unique")
        if unique and plain in self.taken:
            # log.debug("Returns refused")
            return False
        # log.debug("Refuses a name near any protected one")
        if any(score_plain(plain, other) >= self.ceiling for other in self.protected):
            # log.debug("Returns refused")
            return False
        # log.debug("Remembers the name")
        self.taken.add(plain)
        # log.debug("Returns accepted")
        return True


# log.debug("Defines how the planted-records file is read")
def load_firm(path: Path) -> FirmFile:
    """Return the planted records, validated."""
    # log.debug("Parses and validates the file")
    return FirmFile.model_validate(json.loads(path.read_text(encoding="utf-8")))


# log.debug("Defines the plan for the whole database; no I/O, so it can be tested")
def plan_firm(firm: FirmFile, settings: AppSettings) -> Plan:
    """Return every row the database will hold, the same for one seed.

    Raises:
        ValueError: The settings ask for more distinct names than the
            generator can make.
    """
    # log.debug("Seeds the choices")
    rng = random.Random(settings.seed_random)  # noqa: S311 - test data, not security
    # log.debug("Seeds the name generator")
    names = NameGen(settings.seed_random)
    # log.debug("Builds the guard from every protected name")
    guard = _Guard([normalize(n) for n in firm.protected()], settings.match_possible)
    # log.debug("Starts the plan with the planted clients")
    plan = Plan(clients=[(c.name, c.status) for c in firm.clients])
    # log.debug("Marks the planted names as taken")
    guard.taken.update(normalize(name) for name, _ in plan.clients)
    # log.debug("Adds made-up clients")
    _make_clients(plan, settings, rng, names, guard)
    # log.debug("Adds the planted matters and their adverse parties")
    _plant_matters(firm, plan)
    # log.debug("Notes which clients and matters are made up: those after the planted")
    made_up = range(len(firm.clients), len(plan.clients))
    # log.debug("Adds made-up matters for made-up clients")
    _make_matters(plan, settings, rng, made_up)
    # log.debug("Adds made-up adverse parties to made-up matters")
    _make_adverse(plan, settings, rng, names, guard, made_up=made_up, first=len(firm.matters))
    # log.debug("Returns the plan")
    return plan


# log.debug("Defines the made-up clients step")
def _make_clients(
    plan: Plan, settings: AppSettings, rng: random.Random, names: NameGen, guard: _Guard
) -> None:
    """Add made-up clients, companies and people, until the count."""
    # log.debug("Tries a bounded number of times")
    for _ in _attempts(settings.seed_clients - len(plan.clients)):
        # log.debug("Stops when there are enough")
        if len(plan.clients) >= settings.seed_clients:
            # log.debug("Leaves the loop")
            break
        # log.debug("Decides between a company and a person")
        company = rng.random() < CLIENT_COMPANY_SHARE
        # log.debug("Makes the name")
        name = names.company() if company else names.person()
        # log.debug("Skips a name the guard refuses")
        if not guard.accept(name, unique=True):
            # log.debug("Tries again")
            continue
        # log.debug("Notes a company, the kind near duplicates are made from")
        if company:
            # log.debug("Records its position")
            plan.companies.append(len(plan.clients))
        # log.debug("Adds it, former or current")
        plan.clients.append(
            (name, "former" if rng.random() < settings.seed_former_share else "current")
        )
    # log.debug("Refuses to go on short of clients")
    _require(len(plan.clients), settings.seed_clients, "clients")


# log.debug("Defines the planted matters step")
def _plant_matters(firm: FirmFile, plan: Plan) -> None:
    """Add each planted matter and its adverse parties to the plan."""
    # log.debug("Finds each planted client's position")
    position = {name: index for index, (name, _) in enumerate(plan.clients)}
    # log.debug("Adds each matter")
    for matter in firm.matters:
        # log.debug("Adds the matter")
        plan.matters.append((matter.number, position[matter.client], matter.kind, matter.status))
        # log.debug("Adds its adverse parties")
        plan.adverse.extend((name, len(plan.matters) - 1) for name in matter.adverse)


# log.debug("Defines the made-up matters step")
def _make_matters(plan: Plan, settings: AppSettings, rng: random.Random, made_up: range) -> None:
    """Add made-up matters for made-up clients, up to the count."""
    # log.debug("Numbers them from the first made-up number")
    for number in range(FIRST_MATTER, FIRST_MATTER + settings.seed_matters - len(plan.matters)):
        # log.debug("Adds a matter with a client, a kind and a status")
        plan.matters.append(
            (
                f"M-{number}",
                rng.choice(made_up),
                rng.choice(MATTER_KINDS),
                "closed" if rng.random() < settings.seed_closed_share else "open",
            )
        )


# log.debug("Defines the made-up adverse parties step")
def _make_adverse(
    plan: Plan,
    settings: AppSettings,
    rng: random.Random,
    names: NameGen,
    guard: _Guard,
    *,
    made_up: range,
    first: int,
) -> None:
    """Add made-up adverse parties to made-up matters."""
    # log.debug("Tries a bounded number of times")
    for _ in _attempts(settings.seed_adverse_parties - len(plan.adverse)):
        # log.debug("Stops when there are enough")
        if len(plan.adverse) >= settings.seed_adverse_parties:
            # log.debug("Leaves the loop")
            break
        # log.debug("Makes a near duplicate of a made-up company client, sometimes")
        if plan.companies and rng.random() < settings.seed_near_duplicate_share:
            # log.debug("Takes the variants of its name a careless intake makes")
            variants = near_duplicates(plan.clients[rng.choice(plan.companies)][0], rng)
            # log.debug("Picks one, or a new company when there are none")
            name = rng.choice(variants) if variants else names.company()
        else:
            # log.debug("Makes a new company or person")
            name = names.company() if rng.random() < ADVERSE_COMPANY_SHARE else names.person()
        # log.debug("Keeps it when the guard accepts it; repeats are allowed")
        if guard.accept(name, unique=False):
            # log.debug("Adds it to a made-up matter")
            plan.adverse.append((name, rng.randrange(first, len(plan.matters))))
    # log.debug("Refuses to go on short of adverse parties")
    _require(len(plan.adverse), settings.seed_adverse_parties, "adverse parties")


# log.debug("Defines the bounded number of tries for a count")
def _attempts(wanted: int) -> range:
    """Return enough tries to make `wanted` names, or none."""
    # log.debug("Returns the tries")
    return range(max(0, wanted) * TRIES_PER_NAME)


# log.debug("Defines the check that a count was reached")
def _require(have: int, want: int, what: str) -> None:
    """Raise when fewer than `want` were made.

    Raises:
        ValueError: The generator ran out of distinct names.
    """
    # log.debug("Refuses a short count")
    if have < want:
        # log.debug("Explains how to fix it")
        msg = f"made {have} of {want} {what}; lower the [seed] count for {what}"
        # log.debug("Raises the refusal")
        raise ValueError(msg)


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
def seed(store: Store, settings: AppSettings) -> SeedReport:
    """Write the planned rows into an empty database only."""
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
def _counts(connection: sqlite3.Connection) -> tuple[int, int, int]:
    """Return the client, matter and adverse party counts."""
    # log.debug("Counts each table")
    return (
        int(connection.execute("SELECT COUNT(*) FROM clients").fetchone()[0]),
        int(connection.execute("SELECT COUNT(*) FROM matters").fetchone()[0]),
        int(connection.execute("SELECT COUNT(*) FROM adverse_parties").fetchone()[0]),
    )
