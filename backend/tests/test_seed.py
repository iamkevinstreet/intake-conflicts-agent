########################################################################
#                      backend/tests/test_seed.py                      #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           Tests the made-up firm: about 500 names,         #
#                     repeatable, and clear of every planted name.     #
########################################################################
"""Tests for the made-up firm: size, repeatability, guard."""

from __future__ import annotations

import pytest
from kds.logs import get_logger

from intake_agent.config import AppSettings
from intake_agent.core import seed as seed_module
from intake_agent.core.firm import SqliteDirectory
from intake_agent.core.names import normalize, score_plain
from intake_agent.core.seed import load_firm, plan_firm, seed
from intake_agent.core.store import Store

# Module constants
log = get_logger(__name__)


# log.debug("Defines the size test")
def test_about_500_names(store: Store, settings: AppSettings) -> None:
    """300 clients and 200 adverse parties, with 180 matters."""
    # log.debug("Counts the tables")
    counts = SqliteDirectory(store).counts()
    # log.debug("Checks them")
    assert counts == {"clients": 300, "matters": 180, "adverse_parties": 200}


# log.debug("Defines the repeatability test")
def test_the_same_seed_builds_the_same_firm(settings: AppSettings) -> None:
    """Two plans from one seed are identical."""
    # log.debug("Reads the planted records")
    firm = load_firm(settings.data_firm)
    # log.debug("Checks two plans match")
    assert plan_firm(firm, settings) == plan_firm(firm, settings)


# log.debug("Defines the guard test")
def test_no_made_up_name_comes_near_a_planted_or_reserved_one(settings: AppSettings) -> None:
    """Generated names cannot disturb the scenarios' findings."""
    # log.debug("Plans the firm")
    firm = load_firm(settings.data_firm)
    # log.debug("Builds the plan")
    plan = plan_firm(firm, settings)
    # log.debug("Puts every protected name in plain form")
    protected = [normalize(n) for n in firm.protected()]
    # log.debug("Takes the generated names: those after the planted ones")
    made_up = [n for n, _ in plan.clients[len(firm.clients) :]] + [
        n for n, _ in plan.adverse[sum(len(m.adverse) for m in firm.matters) :]
    ]
    # log.debug("Checks none scores at or above possible against any protected name")
    assert not [
        (name, other)
        for name in made_up
        for other in protected
        if score_plain(normalize(name), other) >= settings.match_possible
    ]


# log.debug("Defines the near-duplicate test")
def test_the_firm_holds_near_duplicates(settings: AppSettings) -> None:
    """Some adverse parties are typed variants of clients."""
    # log.debug("Plans the firm")
    plan = plan_firm(load_firm(settings.data_firm), settings)
    # log.debug("Maps each client's plain form to its name")
    clients = {normalize(n): n for n, _ in plan.clients}
    # log.debug("Finds adverse parties that are a client written differently")
    pairs = [a for a, _ in plan.adverse if normalize(a) in clients and a != clients[normalize(a)]]
    # log.debug("Checks there are dozens")
    assert len(pairs) >= 30


# log.debug("Defines the idempotence test")
def test_seeding_twice_changes_nothing(store: Store, settings: AppSettings) -> None:
    """A second seed reports the existing counts and writes nothing."""
    # log.debug("Seeds again")
    report = seed(store, settings)
    # log.debug("Checks nothing was created")
    assert (report.created, report.clients) == (False, 300)


# log.debug("Defines the impossible-count test")
def test_asking_for_too_many_names_fails_clearly(
    settings: AppSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asking for too many names is an error, not a hang."""
    # log.debug("Allows one try per name, so the test is quick")
    monkeypatch.setattr(seed_module, "TRIES_PER_NAME", 1)
    # log.debug("Asks for more clients than there are distinct names")
    greedy = settings.model_copy(update={"seed_clients": 3000})
    # log.debug("Expects the explanation")
    with pytest.raises(ValueError, match="lower the \\[seed\\] count"):
        # log.debug("Plans the firm")
        plan_firm(load_firm(settings.data_firm), greedy)
