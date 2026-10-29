########################################################################
#              backend/src/intake_agent/core/conflicts.py              #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Applies the conflicts rules: what a search returns, how serious each
match is, and the verdict. These are plain functions of the firm's
records and the thresholds in settings, so the evaluation and the tests
can check them without a model. The model never decides a band or a
severity; it reads them.

The rules, for a match at or above the possible threshold:

- An adverse party matching a current client: a conflict when the names
  are exact or likely the same, else review (the same party?).
- An adverse party matching a former client: review (is the new matter
  related to the old one?).
- The prospective client matching a party the firm is against in an open
  matter: a conflict when exact or likely, else review.
- The prospective client matching a party in a closed matter: review.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

from collections.abc import Sequence
from typing import Final

# Third-party
from kds.args import missing, required
from kds.logs import get_logger

# Local
from intake_agent.config import SETTINGS
from intake_agent.core.firm import AdverseRecord, ClientRecord
from intake_agent.core.models import Finding, Match, Recommendation, Severity, Side
from intake_agent.core.names import Band, band, normalize, score_plain

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)
# log.debug("Takes the bands strong enough to call a conflict outright, from the config")
STRONG: Final = SETTINGS.match_strong_bands
# log.debug("Takes the verdict for a finding a person must weigh, from the config")
REVIEW: Final = SETTINGS.verdicts_review
# log.debug("Takes the verdict for a finding that blocks the matter, from the config")
CONFLICT: Final = SETTINGS.verdicts_conflict

########################################################################
#                           Local constants                            #
########################################################################
# log.debug("Orders the verdicts from mildest to strictest")
ORDER: dict[Recommendation, int] = {"clear": 0, "review": 1, "conflict": 2}


########################################################################
#                           Conflicts rules                            #
########################################################################
# log.debug("Defines a search of the clients")
def search_clients(
    records: Sequence[ClientRecord] | None = None,
    query: str | None = None,
    *,
    likely: int | None = None,
    possible: int | None = None,
    limit: int | None = None,
) -> list[Match]:
    """Returns the clients whose names match the query, best first.

    Args:
        records: Every client the firm has, current and former.
            Required.
        query: The name to look for, as the email gives it. Required.
        likely: The lowest score of a likely match. Required.
        possible: The lowest score a person must look at. Required.
        limit: The most matches to return. Required.

    Returns:
        The matching clients, each with its score, band and status,
        best first.
    """
    # log.debug("Takes the records, which the caller must give")
    records = required(records=records)
    # log.debug("Takes the query, which the caller must give")
    query = required(query=query)
    # log.debug("Takes the likely threshold, which the caller must give")
    likely = required(likely=likely)
    # log.debug("Takes the possible threshold, which the caller must give")
    possible = required(possible=possible)
    # log.debug("Takes the limit, which the caller must give")
    limit = required(limit=limit)
    # log.debug("Scores every client's name against the query")
    scored = _scores(query, [r.name for r in records], likely=likely, possible=possible)
    # log.debug("Returns the best, each as a match with the client's status")
    return _best(
        [
            Match(
                kind="client",
                id=records[index].id,
                name=records[index].name,
                score=value,
                band=strength,
                status=records[index].status,
            )
            for index, value, strength in scored
        ],
        limit,
    )


# log.debug("Defines a search of the adverse parties")
def search_adverse(
    records: Sequence[AdverseRecord] | None = None,
    query: str | None = None,
    *,
    likely: int | None = None,
    possible: int | None = None,
    limit: int | None = None,
) -> list[Match]:
    """Returns the adverse parties whose names match, best first.

    Args:
        records: Every party the firm has been against, with its
            matter. Required.
        query: The name to look for, as the email gives it. Required.
        likely: The lowest score of a likely match. Required.
        possible: The lowest score a person must look at. Required.
        limit: The most matches to return. Required.

    Returns:
        The matching parties, each with its score, band, matter and
        the matter's status, best first.
    """
    # log.debug("Takes the records, which the caller must give")
    records = required(records=records)
    # log.debug("Takes the query, which the caller must give")
    query = required(query=query)
    # log.debug("Takes the likely threshold, which the caller must give")
    likely = required(likely=likely)
    # log.debug("Takes the possible threshold, which the caller must give")
    possible = required(possible=possible)
    # log.debug("Takes the limit, which the caller must give")
    limit = required(limit=limit)
    # log.debug("Scores every adverse party's name against the query")
    scored = _scores(query, [r.name for r in records], likely=likely, possible=possible)
    # log.debug("Returns the best, each as a match with its matter")
    return _best(
        [
            Match(
                kind="adverse_party",
                id=records[index].id,
                name=records[index].name,
                score=value,
                band=strength,
                status=records[index].matter_status,
                matter=records[index].matter,
                matter_client=records[index].matter_client,
            )
            for index, value, strength in scored
        ],
        limit,
    )


# log.debug("Defines how serious one match is, and why")
def judge(side: Side | None = None, match: Match | None = None) -> tuple[Severity, str]:
    """Returns the severity of a match and the rule that set it.

    Args:
        side: The searched party's side in the new matter: the client,
            or the other side. Required.
        match: The record the search found. Required.

    Returns:
        The severity, review or conflict, and the rule in words.
    """
    # log.debug("Stops when the caller left out the side")
    if side is None:
        # log.debug("Raises the missing-argument error")
        raise missing(side=side)
    # log.debug("Takes the match, which the caller must give")
    match = required(match=match)
    # log.debug("Notes whether the names are close enough to call outright")
    strong = match.band in STRONG
    # log.debug("Judges an adverse party that matched one of our clients")
    if side == "adverse":
        # log.debug("Calls a strong match with a current client a conflict")
        if strong and match.status == "current":
            # log.debug("Returns conflict")
            return CONFLICT, "the other side is a current client"
        # log.debug("Asks a person about a former client")
        if match.status == "former":
            # log.debug("Returns review")
            return REVIEW, "the other side is a former client: is the matter related?"
        # log.debug("Asks a person whether a possible match is the same party")
        return REVIEW, "the other side may be a current client: is it the same party?"
    # log.debug("Calls a strong match with a party we are against now a conflict")
    if strong and match.status == "open":
        # log.debug("Returns conflict")
        return CONFLICT, f"the firm is against this party now, in {match.matter}"
    # log.debug("Asks a person about a closed matter")
    if match.status == "closed":
        # log.debug("Returns review")
        return REVIEW, f"the firm was against this party in {match.matter}, now closed"
    # log.debug("Asks a person whether a possible match is the same party")
    return REVIEW, f"the firm may be against this party now, in {match.matter}"


# log.debug("Defines the findings for one party's matches")
def findings(
    party: str | None = None, side: Side | None = None, matches: Sequence[Match] | None = None
) -> list[Finding]:
    """Returns a finding for each match, with its severity and why.

    Args:
        party: The party as the draft names it. Required.
        side: The party's side in the new matter. Required.
        matches: The records the party's search found. Required.

    Returns:
        One finding per match, in the matches' order.
    """
    # log.debug("Takes the party, which the caller must give")
    party = required(party=party)
    # log.debug("Stops when the caller left out the side")
    if side is None:
        # log.debug("Raises the missing-argument error")
        raise missing(side=side)
    # log.debug("Takes the matches, which the caller must give")
    matches = required(matches=matches)
    # log.debug("Judges each match")
    judged = [(match, *judge(side, match)) for match in matches]
    # log.debug("Returns them as findings")
    return [
        Finding(party=party, side=side, match=match, severity=severity, why=why)
        for match, severity, why in judged
    ]


# log.debug("Defines the verdict the findings alone support")
def verdict(found: Sequence[Finding] | None = None) -> Recommendation:
    """Returns conflict, review or clear: the most serious finding.

    Args:
        found: Every finding for the draft's parties. Required.

    Returns:
        The most serious finding's severity, or clear when there is
        none.
    """
    # log.debug("Takes the findings, which the caller must give")
    found = required(found=found)
    # log.debug("Returns clear when nothing was found")
    if not found:
        # log.debug("Returns clear")
        return "clear"
    # log.debug("Returns the most serious severity")
    return max((finding.severity for finding in found), key=ORDER.__getitem__)


# log.debug("Defines the stricter of two verdicts")
def stricter(
    first: Recommendation | None = None, second: Recommendation | None = None
) -> Recommendation:
    """Returns whichever verdict is stricter.

    Args:
        first: One verdict, such as the agent's. Required.
        second: The other, such as the checks'. Required.

    Returns:
        The stricter of the two; the first when they are the same.
    """
    # log.debug("Stops when the caller left out the first verdict")
    if first is None:
        # log.debug("Raises the missing-argument error")
        raise missing(first=first)
    # log.debug("Stops when the caller left out the second verdict")
    if second is None:
        # log.debug("Raises the missing-argument error")
        raise missing(second=second)
    # log.debug("Returns the one ranked higher")
    return first if ORDER[first] >= ORDER[second] else second


# log.debug("Defines the scoring shared by both searches")
def _scores(
    query: str | None = None,
    names: Sequence[str] | None = None,
    *,
    likely: int | None = None,
    possible: int | None = None,
) -> list[tuple[int, int, Band]]:
    """Returns (index, score, band) for every name that matches.

    Args:
        query: The name to look for. Required.
        names: The names of the records searched, in order. Required.
        likely: The lowest score of a likely match. Required.
        possible: The lowest score a person must look at. Required.

    Returns:
        For each name at or above the possible threshold, its index in
        names, its score and its band.
    """
    # log.debug("Takes the query, which the caller must give")
    query = required(query=query)
    # log.debug("Takes the names, which the caller must give")
    names = required(names=names)
    # log.debug("Takes the likely threshold, which the caller must give")
    likely = required(likely=likely)
    # log.debug("Takes the possible threshold, which the caller must give")
    possible = required(possible=possible)
    # log.debug("Puts the query in plain form once")
    plain = normalize(query)
    # log.debug("Starts the results")
    out: list[tuple[int, int, Band]] = []
    # log.debug("Scores each name")
    for index, name in enumerate(names):
        # log.debug("Scores the plain forms")
        value = score_plain(plain, normalize(name))
        # log.debug("Bands the score; below possible it is no match")
        strength = band(value, likely=likely, possible=possible)
        # log.debug("Keeps a match")
        if strength is not None:
            # log.debug("Adds its index, score and band")
            out.append((index, value, strength))
    # log.debug("Returns the matches")
    return out


# log.debug("Defines the cut to the best matches")
def _best(found: list[Match] | None = None, limit: int | None = None) -> list[Match]:
    """Returns the `limit` best matches; ties go in name order.

    Args:
        found: The matches a search found, in any order. Required.
        limit: The most matches to keep. Required.

    Returns:
        The matches with the highest scores, best first.
    """
    # log.debug("Takes the matches, which the caller must give")
    found = required(found=found)
    # log.debug("Takes the limit, which the caller must give")
    limit = required(limit=limit)
    # log.debug("Sorts by score, then name, and keeps the first few")
    return sorted(found, key=lambda match: (-match.score, match.name))[:limit]
