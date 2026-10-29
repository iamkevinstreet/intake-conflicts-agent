########################################################################
#                    backend/tests/test_offline.py                     #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           Tests the offline stand-in: what its rules find, #
#                     and the blind spot it documents.                 #
########################################################################
"""Tests for the offline stand-in: what it finds and misses."""

from __future__ import annotations

from kds.logs import get_logger

from intake_agent.config import AppSettings
from intake_agent.core.offline import adapter_for, parties
from intake_agent.core.store import Store

from support import CONFLICT_EMAIL, REQUESTER, service

# Module constants
log = get_logger(__name__)


# log.debug("Defines the extraction test")
def test_the_signature_names_the_client() -> None:
    """The signature's company is the client; others are adverse."""
    # log.debug("Checks both")
    assert parties(CONFLICT_EMAIL) == ("Falcon Ridge Supply LLC", ["Ironwood Builders Inc."])


# log.debug("Defines the person test")
def test_a_person_set_off_by_commas_is_found() -> None:
    """ "our former bookkeeper, Ann Lee, took" names Ann Lee."""
    # log.debug("Builds an email")
    email = "Our former bookkeeper, Ann Lee, took funds.\n\nRuth Cole\nSaffron Lane Bakery LLC"
    # log.debug("Checks the person was found")
    assert parties(email) == ("Saffron Lane Bakery LLC", ["Ann Lee"])


# log.debug("Defines the known limitation")
def test_a_company_without_a_legal_form_is_missed() -> None:
    """The stand-in's blind spot, which a model must cover."""
    # log.debug("Builds an email naming Pinnacle Foods without Corp.")
    email = "Pinnacle Foods poached our manager.\n\nGraham Pike\nThornbury Wholesale Foods LLC"
    # log.debug("Checks nothing adverse was found")
    assert parties(email) == ("Thornbury Wholesale Foods LLC", [])


# log.debug("Defines the end-to-end test")
def test_the_stand_in_runs_an_intake_for_free(settings: AppSettings, store: Store) -> None:
    """Searches, drafts and submits for free, finding the conflict."""
    # log.debug("Runs the intake with the stand-in")
    result = service(settings, store, adapter_for(settings)).run(CONFLICT_EMAIL, REQUESTER)
    # log.debug("Checks the outcome, the verdict and the cost")
    assert (
        result.run.outcome,
        result.draft and result.draft.draft.recommendation,
        result.run.cost_usd,
    ) == ("submitted", "conflict", 0.0)


# log.debug("Defines the automatic-reply test")
def test_an_automatic_reply_is_not_an_intake(settings: AppSettings, store: Store) -> None:
    """Out-of-office text ends the run with no searches and no draft."""
    # log.debug("Runs an automatic reply")
    result = service(settings, store, adapter_for(settings)).run(
        "Automatic reply: I am out of the office until Monday.", REQUESTER
    )
    # log.debug("Checks no tool was called")
    assert (result.run.outcome, result.run.tool_calls) == ("no_draft", 0)
