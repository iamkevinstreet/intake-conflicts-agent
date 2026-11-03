########################################################################
#                                                                      #
#               backend/src/intake_agent/evals/shares.py               #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-03
Last modified on:  2026-11-03

Writes numbers and shares the way people read them, by the same rules
as the case study: a number is rounded half up from the exact stored
value, as the browser does, and a share is never rounded up to 100% or
down to 0%, so 100% means every planted record was found. Standard
library only.
"""

########################################################################
#                                                                      #
#                               Imports                                #
#                                                                      #
########################################################################
# Standard library
from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

# Third-party
from kds.args import required
from kds.logs import get_logger

# Local
from intake_agent.config import SETTINGS

########################################################################
#                                                                      #
#                           Global constants                           #
#                                                                      #
########################################################################
log = get_logger(__name__)
# log.debug("Takes the percent a share of one is, from the config")
PERCENT: Final = SETTINGS.units_percent

########################################################################
#                                                                      #
#                           Local constants                            #
#                                                                      #
########################################################################
# log.debug("Sets the smallest percent shown as a number; below it reads under 0.1")
SMALLEST_SHOWN: Final = 0.05
# log.debug("Sets the percent below which one decimal is shown")
TENTHS_BELOW: Final = 9.95
# log.debug("Sets the percent above which one decimal is shown, rounded down")
TENTHS_ABOVE: Final = 99
# log.debug("Sets the base of the decimals a share is written in")
DECIMAL: Final = 10
# log.debug("Sets the nudge that keeps a float like 99.9 from flooring to 99.8")
NUDGE: Final = 1e-9


########################################################################
#                                                                      #
#                           Written numbers                            #
#                                                                      #
########################################################################
# log.debug("Defines rounding the way JavaScript's toFixed does it")
def fixed(x: float | None = None, places: int | None = None) -> str:
    """Returns x to `places` decimals, halves rounded up, like toFixed.

    The exact stored value is rounded, so the case study and the
    dashboard show the same digits; Python's own format rounds halves
    to even.

    Args:
        x: The number to write. Required.
        places: The decimals to keep. Required.

    Returns:
        The number as text, rounded half up.
    """
    # log.debug("Takes the number, which the caller must give")
    x = required(x=x)
    # log.debug("Takes the decimals, which the caller must give")
    places = required(places=places)
    # log.debug("Rounds a negative number as its opposite, with a minus sign")
    if x < 0:
        # log.debug("Returns the minus sign and the rounded opposite")
        return "-" + fixed(-x, places)
    # log.debug("Returns the exact value rounded half up to the places asked")
    return str(Decimal(x).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


# log.debug("Defines how a share is written")
def pct_label(v: float | None = None, places: int | None = None) -> str:
    """Returns a share as a person reads it.

    100% only when everything was right and 0% only when nothing was,
    so a value just under 100% is never rounded up to it: whole
    percents, one decimal below 10% and above 99%. With `places`, every
    share gets that many decimals, as in a table column, under the same
    two rules.

    Args:
        v: The share, from 0 to 1. Required.
        places: The decimals every share gets in a table column; None
            gives each share the decimals its size calls for.

    Returns:
        The share as a percent, with its sign.
    """
    # log.debug("Takes the share, which the caller must give")
    v = required(v=v)
    # log.debug("Writes a table column's share with its fixed decimals")
    if places is not None:
        # log.debug("Returns the column form")
        return _column(v, places)
    # log.debug("Writes all right as a hundred percent and none right as zero")
    if v >= 1 or v <= 0:
        # log.debug("Returns a hundred or zero percent")
        return "100%" if v >= 1 else "0%"
    # log.debug("Returns the share written as a percent")
    return _percent(v * PERCENT)


# log.debug("Defines a percent strictly between 0 and 100, as written")
def _percent(p: float | None = None) -> str:
    """Returns p with the decimals its size calls for.

    Args:
        p: The percent, strictly between 0 and 100. Required.

    Returns:
        The percent with its sign: under 0.1% for a tiny share, one
        decimal below 10% and above 99% (rounded down), whole between.
    """
    # log.debug("Takes the percent, which the caller must give")
    p = required(p=p)
    # log.debug("Writes a tiny share as under a tenth of a percent, never as zero")
    if p < SMALLEST_SHOWN:
        # log.debug("Returns under a tenth of a percent")
        return "<0.1%"
    # log.debug("Writes a share under ten percent with one decimal")
    if p < TENTHS_BELOW:
        # log.debug("Returns one decimal")
        return f"{fixed(p, 1)}%"
    # log.debug("Writes a share over 99 percent with one decimal, rounded down")
    if p > TENTHS_ABOVE:
        # log.debug("Returns one decimal, never rounded up to a hundred")
        return f"{math.floor(p * DECIMAL + NUDGE) / DECIMAL:.1f}%"
    # log.debug("Returns a whole percent")
    return f"{fixed(p, 0)}%"


# log.debug("Defines a share with a fixed number of decimals")
def _column(v: float | None = None, places: int | None = None) -> str:
    """Returns a share to `places` decimals, never rounded to 0 or 100.

    Used for table columns, where every share has the same decimals.

    Args:
        v: The share, from 0 to 1. Required.
        places: The decimals to keep. Required.

    Returns:
        The percent with its decimals and sign; 0 and 100 only when the
        share is exactly none or all.
    """
    # log.debug("Takes the share, which the caller must give")
    v = required(v=v)
    # log.debug("Takes the decimals, which the caller must give")
    places = required(places=places)
    # log.debug("Finds the smallest step those decimals can show")
    step = float(DECIMAL) ** -places
    # log.debug("Writes all or none right exactly")
    if v >= 1 or v <= 0:
        # log.debug("Returns 100 or 0 with the decimals")
        return f"{PERCENT if v >= 1 else 0:.{places}f}%"
    # log.debug("Writes a share smaller than half a step as under one step")
    if v * PERCENT < step / 2:
        # log.debug("Returns under one step")
        return f"<{step:.{places}f}%"
    # log.debug("Rounds the percent half up")
    shown = fixed(v * PERCENT, places)
    # log.debug("Returns it, held one step under 100 when it would round up")
    return (f"{PERCENT - step:.{places}f}" if float(shown) >= PERCENT else shown) + "%"
