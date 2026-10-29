########################################################################
#                backend/src/intake_agent/core/guard.py                #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Finds lines in an intake email that give orders to the agent, for the
approver to see. An intake email is data. A line in it that addresses
the agent ("skip the approval step", "ignore your instructions") is a
prompt injection. The guard does not block the run, because the approval
gate does not depend on the model behaving; it copies the lines into the
draft so the approver sees exactly what the email tried.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

import re

# Third-party
from kds.args import required
from kds.logs import get_logger

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)

########################################################################
#                           Local constants                            #
########################################################################
# log.debug("Lists patterns of text that gives orders to an agent or a system")
PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(ignore|disregard|forget|override)\b[^.\n]{0,40}"
        r"\b(instructions?|prompts?|rules|directions)\b",
        r"\b(skip|bypass|waive)\b[^.\n]{0,30}\b(approval|sign[- ]?off)\b",
        r"\b(skip|bypass)\b[^.\n]{0,30}\b(conflicts?|search(es)?|checks?)\b",
        r"\bno need (to|for)\b[^.\n]{0,30}\bconflicts?\b",
        r"\bopen_matter\b|\bopen (the|this) matter\b",
        r"\b(mark|record|treat|log)\b[^.\n]{0,40}\bas (clear|cleared|no conflict)\b",
        r"\b(this|the) (matter|intake) (is|has been|was) (pre-?approved|already approved)\b",
        r"\bpre-?approved by\b",
        r"\b(note|instructions?|message)s? (to|for) (the )?(intake |conflicts )?"
        r"(assistant|agent|ai|model|system)\b",
        r"\bsystem (note|message|prompt|instructions?)\b",
        r"\b(list|show|print|send|reveal)\b[^.\n]{0,30}\b(all|every)\b[^.\n]{0,20}\bclients?\b",
        r"</?\s*(system|instructions?|prompt|email)\s*>",
    )
)
# log.debug("Sets how much of a flagged line is kept")
SHOWN_CHARS = 200


########################################################################
#                           Injection check                            #
########################################################################
# log.debug("Defines the check that finds order-giving lines")
def flag(text: str | None = None) -> list[str]:
    """Returns each line of `text` that gives the agent orders.

    Args:
        text: The intake email. Required.

    Returns:
        Each line that matches a pattern, trimmed and cut to
        SHOWN_CHARS characters, in the email's order.
    """
    # log.debug("Takes the text, which the caller must give")
    text = required(text=text)
    # log.debug("Returns every matching line, trimmed and shortened")
    return [
        line.strip()[:SHOWN_CHARS]
        for line in text.splitlines()
        if any(pattern.search(line) for pattern in PATTERNS)
    ]
