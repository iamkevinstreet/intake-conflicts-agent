########################################################################
#                backend/src/intake_agent/core/plan.py                 #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Plans every row of the made-up firm database: the planted records, then
made-up clients, matters and adverse parties until the counts in
settings are reached. A share of the made-up adverse parties are near
duplicates of made-up clients ("Westbrook Cosulting" beside "Westbrook
Consulting LLP"), the mess real intake data has. Every made-up name is
kept below the possible-match score against every planted and reserved
name, so no generated record can change what a scenario should find. The
plan needs no database, so it can be tested on its own, and the same
seed always gives the same plan.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

import random
from dataclasses import dataclass, field

# Third-party
from kds.args import required
from kds.logs import get_logger
from kds.synthetic import NameGen, near_duplicates

# Local
from intake_agent.config import AppSettings
from intake_agent.core.names import normalize, score_plain
from intake_agent.core.planted import FirmFile

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)

########################################################################
#                           Local constants                            #
########################################################################
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


########################################################################
#                           Made-up records                            #
########################################################################
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
    def accept(self, name: str | None = None, *, unique: bool | None = None) -> bool:
        """Returns whether a name may be used, and remembers it if so.

        Args:
            name: A made-up name the generator offers. Required.
            unique: True when the name must not repeat one already
                used, as for clients. Required.

        Returns:
            True when the name is far from every protected name (and
            new, when it must be); the name is then taken.
        """
        # log.debug("Takes the name, which the caller must give")
        name = required(name=name)
        # log.debug("Takes whether the name must be new, which the caller must give")
        unique = required(unique=unique)
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


# log.debug("Defines the plan for the whole database; no I/O, so it can be tested")
def plan_firm(firm: FirmFile | None = None, settings: AppSettings | None = None) -> Plan:
    """Returns every row the database will hold, the same for one seed.

    Args:
        firm: The planted records. Required.
        settings: The settings that give the seed, the counts and the
            possible-match score made-up names must stay below.
            Required.

    Returns:
        Every client, matter and adverse party to insert, the planted
        ones first.

    Raises:
        ValueError: The settings ask for more distinct names than the
            generator can make.
    """
    # log.debug("Takes the planted records, which the caller must give")
    firm = required(firm=firm)
    # log.debug("Takes the settings, which the caller must give")
    settings = required(settings=settings)
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
    plan: Plan | None = None,
    settings: AppSettings | None = None,
    rng: random.Random | None = None,
    names: NameGen | None = None,
    guard: _Guard | None = None,
) -> None:
    """Adds made-up clients, companies and people, until the count.

    Args:
        plan: The plan so far, which the clients are added to.
            Required.
        settings: The settings that give the count and the share of
            former clients. Required.
        rng: The seeded source of every random choice. Required.
        names: The seeded maker of company and person names. Required.
        guard: The check that keeps made-up names clear of protected
            ones. Required.

    Raises:
        ValueError: The generator ran out of distinct names.
    """
    # log.debug("Takes the plan, which the caller must give")
    plan = required(plan=plan)
    # log.debug("Takes the settings, which the caller must give")
    settings = required(settings=settings)
    # log.debug("Takes the seeded random source, which the caller must give")
    rng = required(rng=rng)
    # log.debug("Takes the name maker, which the caller must give")
    names = required(names=names)
    # log.debug("Takes the guard, which the caller must give")
    guard = required(guard=guard)
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
def _plant_matters(firm: FirmFile | None = None, plan: Plan | None = None) -> None:
    """Adds each planted matter and its adverse parties to the plan.

    Args:
        firm: The planted records, whose matters are added. Required.
        plan: The plan so far, which already holds the planted
            clients. Required.
    """
    # log.debug("Takes the planted records, which the caller must give")
    firm = required(firm=firm)
    # log.debug("Takes the plan, which the caller must give")
    plan = required(plan=plan)
    # log.debug("Finds each planted client's position")
    position = {name: index for index, (name, _) in enumerate(plan.clients)}
    # log.debug("Adds each matter")
    for matter in firm.matters:
        # log.debug("Adds the matter")
        plan.matters.append((matter.number, position[matter.client], matter.kind, matter.status))
        # log.debug("Adds its adverse parties")
        plan.adverse.extend((name, len(plan.matters) - 1) for name in matter.adverse)


# log.debug("Defines the made-up matters step")
def _make_matters(
    plan: Plan | None = None,
    settings: AppSettings | None = None,
    rng: random.Random | None = None,
    made_up: range | None = None,
) -> None:
    """Adds made-up matters for made-up clients, up to the count.

    Args:
        plan: The plan so far, which the matters are added to.
            Required.
        settings: The settings that give the count and the share of
            closed matters. Required.
        rng: The seeded source of every random choice. Required.
        made_up: The positions of the made-up clients, which the
            matters are given to. Required.
    """
    # log.debug("Takes the plan, which the caller must give")
    plan = required(plan=plan)
    # log.debug("Takes the settings, which the caller must give")
    settings = required(settings=settings)
    # log.debug("Takes the seeded random source, which the caller must give")
    rng = required(rng=rng)
    # log.debug("Takes the made-up client positions, which the caller must give")
    made_up = required(made_up=made_up)
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
    plan: Plan | None = None,
    settings: AppSettings | None = None,
    rng: random.Random | None = None,
    names: NameGen | None = None,
    guard: _Guard | None = None,
    *,
    made_up: range | None = None,
    first: int | None = None,
) -> None:
    """Adds made-up adverse parties to made-up matters.

    Args:
        plan: The plan so far, which the parties are added to.
            Required.
        settings: The settings that give the count and the share of
            near duplicates. Required.
        rng: The seeded source of every random choice. Required.
        names: The seeded maker of company and person names. Required.
        guard: The check that keeps made-up names clear of protected
            ones. Required.
        made_up: The positions of the made-up clients, whose matters
            follow the planted ones. Required.
        first: The position of the first made-up matter; each party
            goes to a matter from there on. Required.

    Raises:
        ValueError: The generator ran out of acceptable names.
    """
    # log.debug("Takes the plan, which the caller must give")
    plan = required(plan=plan)
    # log.debug("Takes the settings, which the caller must give")
    settings = required(settings=settings)
    # log.debug("Takes the seeded random source, which the caller must give")
    rng = required(rng=rng)
    # log.debug("Takes the name maker, which the caller must give")
    names = required(names=names)
    # log.debug("Takes the guard, which the caller must give")
    guard = required(guard=guard)
    # log.debug("Takes the made-up client positions, which the caller must give")
    made_up = required(made_up=made_up)
    # log.debug("Takes the first made-up matter's position, which the caller must give")
    first = required(first=first)
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
def _attempts(wanted: int | None = None) -> range:
    """Returns enough tries to make `wanted` names, or none.

    Args:
        wanted: How many more names are needed; zero or fewer needs
            none. Required.

    Returns:
        TRIES_PER_NAME tries for each name wanted.
    """
    # log.debug("Takes the number of names wanted, which the caller must give")
    wanted = required(wanted=wanted)
    # log.debug("Returns the tries")
    return range(max(0, wanted) * TRIES_PER_NAME)


# log.debug("Defines the check that a count was reached")
def _require(have: int | None = None, want: int | None = None, what: str | None = None) -> None:
    """Raises when fewer than `want` were made.

    Args:
        have: How many were made. Required.
        want: How many the settings ask for. Required.
        what: What was counted, as the error names it, such as
            clients. Required.

    Raises:
        ValueError: The generator ran out of distinct names.
    """
    # log.debug("Takes the count made, which the caller must give")
    have = required(have=have)
    # log.debug("Takes the count asked for, which the caller must give")
    want = required(want=want)
    # log.debug("Takes what was counted, which the caller must give")
    what = required(what=what)
    # log.debug("Refuses a short count")
    if have < want:
        # log.debug("Explains how to fix it")
        msg = f"made {have} of {want} {what}; lower the [seed] count for {what}"
        # log.debug("Raises the refusal")
        raise ValueError(msg)
