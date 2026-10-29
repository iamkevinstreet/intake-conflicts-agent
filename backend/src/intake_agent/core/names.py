########################################################################
#                backend/src/intake_agent/core/names.py                #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           Plain forms of party names and how alike two     #
#                     names are, so typed variants still match.        #
########################################################################
"""Party names: one plain form for comparing, and a score for matching.

Intake data is typed by people, so the same company arrives as "ACME
Logistics LLC", "Acme Logistic Inc." and "AcmeLogistics". Comparing
plain forms (lower case, no punctuation, no legal suffix) and taking
the best of three scores catches those variants; the bands then say
how sure the match is. A person decides every match below "exact".
"""

from __future__ import annotations

import re
from typing import Literal

from kds.logs import get_logger
from rapidfuzz import fuzz

# Module constants
log = get_logger(__name__)
# log.debug("Lists how sure a match is, strongest first")
Band = Literal["exact", "likely", "possible"]
# log.debug("Lists legal-form words that say nothing about who a party is")
LEGAL_FORMS = frozenset(
    "llc inc incorporated corp corporation co company llp lp ltd limited plc pllc pc group".split()
)
# log.debug("Matches anything that is not a letter, digit or space")
PUNCTUATION_RE = re.compile(r"[^\w\s]|_")
# log.debug("Matches runs of whitespace")
SPACES_RE = re.compile(r"\s+")
# log.debug("Sets the score of two identical plain forms")
EXACT = 100


# log.debug("Defines the plain form two names are compared in")
def normalize(name: str) -> str:
    """Return the name lowercased, without punctuation or legal form.

    "Acme Logistics, L.L.C." and "ACME LOGISTICS" both become "acme
    logistics". A name that is only a legal form keeps one word.
    """
    # log.debug("Lowercases, spells out ampersands, and closes up L.L.C. and Inc.")
    text = name.casefold().replace("&", " and ").replace(".", "")
    # log.debug("Turns other punctuation and hyphens into spaces")
    text = SPACES_RE.sub(" ", PUNCTUATION_RE.sub(" ", text)).strip()
    # log.debug("Splits the name into words")
    words = text.split()
    # log.debug("Drops a leading 'the'")
    if len(words) > 1 and words[0] == "the":
        # log.debug("Keeps the words after it")
        words = words[1:]
    # log.debug("Drops legal-form words from the end, keeping at least one word")
    while len(words) > 1 and words[-1] in LEGAL_FORMS:
        # log.debug("Drops the last word")
        words.pop()
    # log.debug("Returns the words joined by single spaces")
    return " ".join(words)


# log.debug("Defines how alike two names are, from 0 to 100")
def score(first: str, second: str) -> int:
    """Return how alike two names are, from 0 to 100."""
    # log.debug("Scores the plain forms")
    return score_plain(normalize(first), normalize(second))


# log.debug("Defines the score of two names already in plain form")
def score_plain(first: str, second: str) -> int:
    """Return how alike two plain forms are; 100 only when the same.

    The best of three comparisons: letter by letter, with the words
    sorted (so "okafor riley" meets "riley okafor"), and with the
    spaces removed (so "acmelogistics" meets "acme logistics").
    """
    # log.debug("Returns 100 at once when the plain forms are the same")
    if first == second:
        # log.debug("Returns the exact score")
        return EXACT
    # log.debug("Returns the best of the three, rounded down, below 100")
    return min(
        EXACT - 1,
        int(
            max(
                fuzz.ratio(first, second),
                fuzz.token_sort_ratio(first, second),
                fuzz.ratio(first.replace(" ", ""), second.replace(" ", "")),
            )
        ),
    )


# log.debug("Defines the band a score falls in")
def band(value: int, *, likely: int, possible: int) -> Band | None:
    """Return how sure a match with this score is; None below possible.

    Args:
        value: The score, 0 to 100.
        likely: The lowest score of a likely match.
        possible: The lowest score a person must look at.
    """
    # log.debug("Calls a perfect score exact")
    if value >= EXACT:
        # log.debug("Returns exact")
        return "exact"
    # log.debug("Calls a score at or above the likely threshold likely")
    if value >= likely:
        # log.debug("Returns likely")
        return "likely"
    # log.debug("Returns possible at or above that threshold, else no match")
    return "possible" if value >= possible else None
