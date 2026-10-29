########################################################################
#                backend/src/intake_agent/core/names.py                #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Puts party names in a plain form and scores how alike two names are, so
typed variants still match. Intake data is typed by people, so the same
company arrives as "ACME Logistics LLC", "Acme Logistic Inc." and
"AcmeLogistics". Comparing plain forms (lower case, no punctuation, no
legal suffix) and taking the best of three scores catches those
variants; the bands then say how sure the match is. A person decides
every match below "exact".
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

import re
from typing import Literal

# Third-party
from kds.args import required
from kds.logs import get_logger
from rapidfuzz import fuzz

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)

########################################################################
#                           Local constants                            #
########################################################################
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


########################################################################
#                            Name matching                             #
########################################################################
# log.debug("Defines the plain form two names are compared in")
def normalize(name: str | None = None) -> str:
    """Returns the name lowercased, without punctuation or legal form.

    "Acme Logistics, L.L.C." and "ACME LOGISTICS" both become "acme
    logistics". A name that is only a legal form keeps one word.

    Args:
        name: A party's name as someone typed it. Required.

    Returns:
        The plain form: lower case, single spaces, no punctuation, no
        leading "the" and no legal form at the end.
    """
    # log.debug("Takes the name, which the caller must give")
    name = required(name=name)
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
def score(first: str | None = None, second: str | None = None) -> int:
    """Returns how alike two names are, from 0 to 100.

    Args:
        first: One name, as typed. Required.
        second: The other name, as typed. Required.

    Returns:
        The score of their plain forms: 100 only when those are the
        same.
    """
    # log.debug("Takes the first name, which the caller must give")
    first = required(first=first)
    # log.debug("Takes the second name, which the caller must give")
    second = required(second=second)
    # log.debug("Scores the plain forms")
    return score_plain(normalize(first), normalize(second))


# log.debug("Defines the score of two names already in plain form")
def score_plain(first: str | None = None, second: str | None = None) -> int:
    """Returns how alike two plain forms are; 100 only when the same.

    The best of three comparisons: letter by letter, with the words
    sorted (so "okafor riley" meets "riley okafor"), and with the
    spaces removed (so "acmelogistics" meets "acme logistics").

    Args:
        first: One name, already in plain form. Required.
        second: The other name, already in plain form. Required.

    Returns:
        100 for the same plain form, else the best of the three
        comparisons, rounded down and at most 99.
    """
    # log.debug("Takes the first plain form, which the caller must give")
    first = required(first=first)
    # log.debug("Takes the second plain form, which the caller must give")
    second = required(second=second)
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
def band(
    value: int | None = None, *, likely: int | None = None, possible: int | None = None
) -> Band | None:
    """Returns how sure a match with this score is; None below possible.

    Args:
        value: The score, 0 to 100. Required.
        likely: The lowest score of a likely match. Required.
        possible: The lowest score a person must look at. Required.

    Returns:
        exact for 100, likely from the likely threshold, possible from
        the possible threshold, or None for no match.
    """
    # log.debug("Takes the score, which the caller must give")
    value = required(value=value)
    # log.debug("Takes the likely threshold, which the caller must give")
    likely = required(likely=likely)
    # log.debug("Takes the possible threshold, which the caller must give")
    possible = required(possible=possible)
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
