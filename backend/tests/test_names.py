########################################################################
#                     backend/tests/test_names.py                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Tests name matching: plain forms, scores, bands, and every near
duplicate caught.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

import random

# Third-party
import pytest
from kds.logs import get_logger
from kds.synthetic import NameGen, near_duplicates

# Local
from intake_agent.core.names import band, normalize, score

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)


########################################################################
#                         Name matching tests                          #
########################################################################
# log.debug("Defines the plain-form cases")
@pytest.mark.parametrize(
    ("name", "plain"),
    [
        ("ACME Logistics LLC", "acme logistics"),
        ("Acme Logistics, L.L.C.", "acme logistics"),
        ("The Granite Roofing Co.", "granite roofing"),
        ("Okafor & Lindqvist LLP", "okafor and lindqvist"),
        ("Delta-Logistics", "delta logistics"),
        ("  Harborview   Dental Group ", "harborview dental"),
        ("Inc.", "inc"),
    ],
)
def test_normalize(name: str, plain: str) -> None:
    """Case, punctuation, legal forms and a leading 'the' fall away.

    Args:
        name: A name as someone typed it.
        plain: Its expected plain form.
    """
    # log.debug("Checks the plain form")
    assert normalize(name) == plain


# log.debug("Defines the test that only the same plain form scores 100")
def test_exact_means_the_same_plain_form() -> None:
    """Variants that differ in spacing score high, but below 100."""
    # log.debug("Checks the same plain form scores 100")
    assert score("Pinnacle Foods", "Pinnacle Foods Corp.") == 100
    # log.debug("Checks a name with its spaces removed scores 99")
    assert score("AcmeLogistics", "Acme Logistics") == 99


# log.debug("Defines the test that word order does not matter")
def test_last_name_first() -> None:
    """Last name first is likely the same person."""
    # log.debug("Checks the band")
    assert band(score("Ellison, Rowan", "Rowan Ellison"), likely=92, possible=80) == "likely"


# log.debug("Defines the test of the case study's own example")
def test_the_case_study_pair_is_likely() -> None:
    """The case study's Acme pair is a likely match."""
    # log.debug("Checks the band")
    assert band(score("Acme Logistic Inc.", "ACME Logistics LLC"), likely=92, possible=80) == (
        "likely"
    )


# log.debug("Defines the test that different companies sharing a word do not match")
def test_a_shared_first_word_is_not_a_match() -> None:
    """Ironwood Bakery is not Ironwood Builders."""
    # log.debug("Checks there is no band")
    assert band(
        score("Ironwood Bakery Co.", "Ironwood Builders Inc."), likely=92, possible=80
    ) is (None)


# log.debug("Defines the test that every near duplicate a careless intake makes is caught")
def test_near_duplicates_score_at_least_possible() -> None:
    """Every variant kds.synthetic makes of 200 companies is a match."""
    # log.debug("Seeds the generators")
    names, rng = NameGen(3), random.Random(3)  # noqa: S311 - test data, not security
    # log.debug("Makes 200 companies")
    companies = [names.company() for _ in range(200)]
    # log.debug("Scores every variant against its company")
    misses = [
        (company, variant)
        for company in companies
        for variant in near_duplicates(company, rng)
        if score(company, variant) < 80
    ]
    # log.debug("Checks none fell below the possible threshold")
    assert misses == []


# log.debug("Defines the band boundaries")
@pytest.mark.parametrize(
    ("value", "expected"), [(100, "exact"), (92, "likely"), (91, "possible"), (80, "possible")]
)
def test_band_boundaries(value: int, expected: str) -> None:
    """The thresholds are inclusive.

    Args:
        value: A score at a threshold, or just below one.
        expected: The band the score falls in.
    """
    # log.debug("Checks the band")
    assert band(value, likely=92, possible=80) == expected


# log.debug("Defines the test below the possible threshold")
def test_below_possible_is_no_match() -> None:
    """79 is no match at all."""
    # log.debug("Checks None")
    assert band(79, likely=92, possible=80) is None
