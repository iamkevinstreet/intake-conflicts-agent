########################################################################
#                backend/intake_agent/core/conflicts.py                #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           The conflicts rules: what a search returns, how  #
#                     serious each match is, and the verdict.          #
########################################################################
"""The conflicts rules: what a search returns and what a match means.

These are plain functions of the firm's records and the thresholds in
settings, so the evaluation and the tests can check them without a
model. The model never decides a band or a severity; it reads them.

The rules, for a match at or above the possible threshold:

- An adverse party matching a current client: a conflict when the
  names are exact or likely the same, else review (the same party?).
- An adverse party matching a former client: review (is the new
  matter related to the old one?).
- The prospective client matching a party the firm is against in an
  open matter: a conflict when exact or likely, else review.
- The prospective client matching a party in a closed matter: review.
"""

from __future__ import annotations

from collections.abc import Sequence

from kds.logs import get_logger

from intake_agent.core.firm import AdverseRecord, ClientRecord
from intake_agent.core.models import Finding, Match, Recommendation, Severity, Side
from intake_agent.core.names import Band, band, normalize, score_plain

# Module constants
log = get_logger(__name__)
# log.debug("Orders the verdicts from mildest to strictest")
ORDER: dict[Recommendation, int] = {"clear": 0, "review": 1, "conflict": 2}
# log.debug("Lists the bands strong enough to call a conflict outright")
STRONG = frozenset({"exact", "likely"})
# log.debug("Names the verdict for a finding a person must weigh")
REVIEW: Severity = "review"
# log.debug("Names the verdict for a finding that blocks the matter")
CONFLICT: Severity = "conflict"


# log.debug("Defines a search of the clients")
def search_clients(
    records: Sequence[ClientRecord], query: str, *, likely: int, possible: int, limit: int
) -> list[Match]:
    """Return the clients whose names match the query, best first."""
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
    records: Sequence[AdverseRecord], query: str, *, likely: int, possible: int, limit: int
) -> list[Match]:
    """Return the adverse parties whose names match, best first."""
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
def judge(side: Side, match: Match) -> tuple[Severity, str]:
    """Return the severity of a match and the rule that set it."""
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
def findings(party: str, side: Side, matches: Sequence[Match]) -> list[Finding]:
    """Return a finding for each match, with its severity and why."""
    # log.debug("Judges each match")
    judged = [(match, *judge(side, match)) for match in matches]
    # log.debug("Returns them as findings")
    return [
        Finding(party=party, side=side, match=match, severity=severity, why=why)
        for match, severity, why in judged
    ]


# log.debug("Defines the verdict the findings alone support")
def verdict(found: Sequence[Finding]) -> Recommendation:
    """Return conflict, review or clear: the most serious finding."""
    # log.debug("Returns clear when nothing was found")
    if not found:
        # log.debug("Returns clear")
        return "clear"
    # log.debug("Returns the most serious severity")
    return max((finding.severity for finding in found), key=ORDER.__getitem__)


# log.debug("Defines the stricter of two verdicts")
def stricter(first: Recommendation, second: Recommendation) -> Recommendation:
    """Return whichever verdict is stricter."""
    # log.debug("Returns the one ranked higher")
    return first if ORDER[first] >= ORDER[second] else second


# log.debug("Defines the scoring shared by both searches")
def _scores(
    query: str, names: Sequence[str], *, likely: int, possible: int
) -> list[tuple[int, int, Band]]:
    """Return (index, score, band) for every name that matches."""
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
def _best(found: list[Match], limit: int) -> list[Match]:
    """Return the `limit` best matches; ties go in name order."""
    # log.debug("Sorts by score, then name, and keeps the first few")
    return sorted(found, key=lambda match: (-match.score, match.name))[:limit]
