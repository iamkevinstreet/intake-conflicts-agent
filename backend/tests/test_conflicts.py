########################################################################
#                   backend/tests/test_conflicts.py                    #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Tests the conflicts rules: the severity table, the verdict and both
searches.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

# Third-party
import pytest
from kds.args import required
from kds.logs import get_logger

# Local
from intake_agent.core.conflicts import (
    findings,
    judge,
    search_adverse,
    search_clients,
    stricter,
    verdict,
)
from intake_agent.core.firm import AdverseRecord, ClientRecord
from intake_agent.core.models import Match, Side

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)

########################################################################
#                           Local constants                            #
########################################################################
# log.debug("Sets a few clients to search")
CLIENTS = [
    ClientRecord(1, "ACME Logistics LLC", "current"),
    ClientRecord(2, "Northgate Staffing Partners LLC", "former"),
    ClientRecord(3, "Acme Medical Corp.", "current"),
]
# log.debug("Sets a few adverse parties to search")
ADVERSE = [
    AdverseRecord(1, "Summit Ridge Properties LLC", "M-1001", "open", "Granite Roofing Co."),
    AdverseRecord(2, "Westbrook Transport Inc.", "M-1002", "closed", "Bennett Analytics Inc."),
]


########################################################################
#                        Conflicts rules tests                         #
########################################################################
# log.debug("Defines a match for the severity table")
def _match(kind: str | None = None, band: str | None = None, status: str | None = None) -> Match:
    """Returns a match with the given table, band and status.

    Args:
        kind: The table the match came from: client or adverse_party.
            Required.
        band: How sure the match is. Required.
        status: The client's or the matter's status. Required.

    Returns:
        The match, with a fixed id, name, score and matter.
    """
    # log.debug("Takes the kind, which the caller must give")
    kind = required(kind=kind)
    # log.debug("Takes the band, which the caller must give")
    band = required(band=band)
    # log.debug("Takes the status, which the caller must give")
    status = required(status=status)
    # log.debug("Returns it")
    return Match.model_validate(
        {
            "kind": kind,
            "id": 1,
            "name": "X",
            "score": 90,
            "band": band,
            "status": status,
            "matter": "M-1001",
        }
    )


# log.debug("Defines the six rows of the severity table")
@pytest.mark.parametrize(
    ("side", "kind", "band", "status", "severity"),
    [
        ("adverse", "client", "exact", "current", "conflict"),
        ("adverse", "client", "likely", "current", "conflict"),
        ("adverse", "client", "possible", "current", "review"),
        ("adverse", "client", "exact", "former", "review"),
        ("client", "adverse_party", "likely", "open", "conflict"),
        ("client", "adverse_party", "possible", "open", "review"),
        ("client", "adverse_party", "exact", "closed", "review"),
    ],
)
def test_severity_table(side: Side, kind: str, band: str, status: str, severity: str) -> None:
    """Each rule in the module's table gives its severity.

    Args:
        side: The searched party's side in the new matter.
        kind: The table the match came from.
        band: How sure the match is.
        status: The client's or the matter's status.
        severity: The severity the rule gives.
    """
    # log.debug("Checks the severity")
    assert judge(side, _match(kind, band, status))[0] == severity


# log.debug("Defines the test of the verdict")
def test_verdict_is_the_most_serious_finding() -> None:
    """No findings: clear; any conflict: conflict; else review."""
    # log.debug("Builds a review finding and a conflict finding")
    review = findings("A", "adverse", [_match("client", "possible", "current")])
    # log.debug("Builds the conflict finding")
    conflict = findings("B", "adverse", [_match("client", "exact", "current")])
    # log.debug("Checks all three verdicts")
    assert (verdict([]), verdict(review), verdict(review + conflict)) == (
        "clear",
        "review",
        "conflict",
    )


# log.debug("Defines the test of the stricter verdict")
def test_stricter() -> None:
    """The verdict shown is the stricter of the two."""
    # log.debug("Checks both orders")
    assert (stricter("clear", "review"), stricter("conflict", "review")) == ("review", "conflict")


# log.debug("Defines the client search test")
def test_search_clients_finds_variants_best_first() -> None:
    """A typed variant finds the client; another Acme does not."""
    # log.debug("Searches for the case study's variant")
    found = search_clients(CLIENTS, "Acme Logistic Inc.", likely=92, possible=80, limit=5)
    # log.debug("Checks the client was found, likely, and nothing weak came with it")
    assert [(m.name, m.band) for m in found] == [("ACME Logistics LLC", "likely")]


# log.debug("Defines the adverse search test")
def test_search_adverse_carries_the_matter() -> None:
    """An adverse match names the matter, its status and client."""
    # log.debug("Searches the adverse parties")
    (found,) = search_adverse(ADVERSE, "Summit Ridge Properties", likely=92, possible=80, limit=5)
    # log.debug("Checks the matter details")
    assert (found.band, found.matter, found.status, found.matter_client) == (
        "exact",
        "M-1001",
        "open",
        "Granite Roofing Co.",
    )


# log.debug("Defines the limit test")
def test_search_limit() -> None:
    """A limit of one keeps only the best match."""
    # log.debug("Searches with a low threshold so both Acmes match")
    found = search_clients(CLIENTS, "Acme", likely=92, possible=10, limit=1)
    # log.debug("Checks one came back")
    assert len(found) == 1
