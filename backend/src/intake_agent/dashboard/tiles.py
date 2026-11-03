########################################################################
#                                                                      #
#             backend/src/intake_agent/dashboard/tiles.py              #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-03
Last modified on:  2026-11-03

Builds the headline tiles: each measure for the run in focus, and how
it moved against the second run picked. A change that rounds to
nothing at the precision shown is no change; any other gets its
direction and whether that is for the better. Twenty scenarios are
too few to tell a change from run-to-run noise with a test, so the
tiles do not try; the reader weighs each change against the counts.
"""

########################################################################
#                                                                      #
#                               Imports                                #
#                                                                      #
########################################################################
# Standard library
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal, TypedDict

# Third-party
import pandas as pd
from kds.args import required
from kds.logs import get_logger

# Local
from intake_agent.config import SETTINGS
from intake_agent.dashboard.theme import dollars
from intake_agent.evals.shares import fixed, pct_label

########################################################################
#                                                                      #
#                           Global constants                           #
#                                                                      #
########################################################################
log = get_logger(__name__)
# log.debug("Takes the run id column, from the config")
RUN_ID: Final = SETTINGS.columns_run_id
# log.debug("Takes the runs table's cost per scenario column, from the config")
COST_PER_SCENARIO: Final = SETTINGS.columns_cost_per_scenario
# log.debug("Takes the percent a share of one is, from the config")
PERCENT: Final = SETTINGS.units_percent

########################################################################
#                                                                      #
#                           Local constants                            #
#                                                                      #
########################################################################
# log.debug("Names a rise")
UP: Final = "up"
# log.debug("Names a fall")
DOWN: Final = "down"
# log.debug("Sets the words for a change that rounds to nothing")
NO_CHANGE: Final = "no change"
# log.debug("Lists the digits that show a change survived rounding")
NONZERO_DIGITS: Final = "123456789"
# log.debug("Sets the smallest difference that is not zero")
TINY: Final = 1e-12


########################################################################
#                                                                      #
#                            Headline tiles                            #
#                                                                      #
########################################################################
# log.debug("Defines one headline measure")
@dataclass(frozen=True)
class Tile:
    """One headline measure, in the words the case study uses.

    Attributes:
        column: The runs table column it shows.
        label: What the tile calls it.
        value: How its value is written.
        better: Which way is better, up or down.
        change: How the size of a change is written; like the value
            when None.
    """

    # log.debug("Holds the runs table column")
    column: str
    # log.debug("Holds the tile's label")
    label: str
    # log.debug("Holds how the value is written")
    value: Callable[[float], str]
    # log.debug("Holds which way is better")
    better: Literal["up", "down"]
    # log.debug("Holds how the size of a change is written, when not like the value")
    change: Callable[[float], str] | None = None


# log.debug("Defines one tile as the page shows it")
class TileRow(TypedDict):
    """One tile: its measure, label, value, change and tone.

    The change is None when no second run is picked; good is None when
    there is no change.
    """

    # log.debug("Holds the runs table column")
    measure: str
    # log.debug("Holds the label")
    label: str
    # log.debug("Holds the value as written")
    value: str
    # log.debug("Holds the change as written, with its direction")
    delta: str | None
    # log.debug("Holds whether the change is for the better")
    good: bool | None


# log.debug("Defines how a change in a share is written")
def _points(size: float | None = None) -> str:
    """Returns the size of a change in a share, in percentage points.

    Args:
        size: The size of the change in a share, from 0 to 1.
            Required.

    Returns:
        The change in percentage points, to one decimal.
    """
    # log.debug("Takes the size, which the caller must give")
    size = required(size=size)
    # log.debug("Returns the points, to one decimal")
    return f"{fixed(size * PERCENT, 1)} pts"


# log.debug("Defines how a count is written")
def _whole(count: float | None = None) -> str:
    """Returns a count as a whole number.

    Args:
        count: The count. Required.

    Returns:
        The count with no decimals.
    """
    # log.debug("Takes the count, which the caller must give")
    count = required(count=count)
    # log.debug("Returns the whole number")
    return fixed(count, 0)


# log.debug("Defines how a time in seconds is written")
def _seconds(seconds: float | None = None) -> str:
    """Returns a time in seconds, to one decimal.

    Args:
        seconds: The time, in seconds. Required.

    Returns:
        The time in seconds, to one decimal.
    """
    # log.debug("Takes the time, which the caller must give")
    seconds = required(seconds=seconds)
    # log.debug("Returns the seconds")
    return f"{fixed(seconds, 1)} s"


# Plain-language measures, in the words the case study uses: the
# column, its label, how to write it, which way is better, and how to
# write a change when not like the value.
# log.debug("Lists the seven tiles in the order they are shown")
TILES: Final = (
    Tile("conflict_recall", "Planted records found", pct_label, UP, _points),
    Tile("false_positive_rate", "Clean scenarios shown as a conflict", pct_label, DOWN, _points),
    Tile("escalation", "Ambiguous scenarios the agent marked review", pct_label, UP, _points),
    Tile("failure_handling", "Failures handled", pct_label, UP, _points),
    Tile("opened_without_approval", "Matters opened without approval", _whole, DOWN),
    Tile("median_seconds", "Seconds per scenario, typical", _seconds, DOWN),
    Tile(COST_PER_SCENARIO, "Cost per scenario", dollars, DOWN),
)


# log.debug("Defines the tiles for the runs picked")
def tile_rows(
    runs_df: pd.DataFrame | None = None, run_ids: Sequence[str] | None = None
) -> list[TileRow]:
    """Returns each measure for the run in focus, and how it moved.

    It moved against the second run picked.

    Args:
        runs_df: The runs table from `frames`. Required.
        run_ids: The runs picked, the run in focus first. Required.

    Returns:
        A row per tile, in the order shown; none when no run is picked.
    """
    # log.debug("Takes the runs table, which the caller must give")
    runs_df = required(runs_df=runs_df)
    # log.debug("Takes the run ids, which the caller must give")
    run_ids = required(run_ids=run_ids)
    # log.debug("Shows no tiles when no run is picked")
    if not run_ids:
        # log.debug("Returns no rows")
        return []
    # log.debug("Takes the run in focus")
    now = runs_df[runs_df[RUN_ID] == run_ids[0]].iloc[0]
    # log.debug("Takes the run to compare with, when a second is picked")
    then = runs_df[runs_df[RUN_ID] == run_ids[1]].iloc[0] if len(run_ids) > 1 else None
    # log.debug("Returns a row per tile")
    return [_row(tile, now, then) for tile in TILES]


# log.debug("Defines one tile's row")
def _row(
    tile: Tile | None = None,
    now: pd.Series[Any] | None = None,
    then: pd.Series[Any] | None = None,
) -> TileRow:
    """Returns the tile for the run in focus, with its change if any.

    Args:
        tile: The tile. Required.
        now: The run in focus's row of the runs table. Required.
        then: The second run's row, to compare with; None when only
            one run is picked.

    Returns:
        The tile's row, as the page shows it.
    """
    # log.debug("Takes the tile, which the caller must give")
    tile = required(tile=tile)
    # log.debug("Takes the run in focus, which the caller must give")
    now = required(now=now)
    # log.debug("Reads the value, a missing one as zero")
    value = _measure(now, tile.column)
    # log.debug("Reads the earlier run's value, when there is one, a missing one as zero")
    before = None if then is None else _measure(then, tile.column)
    # log.debug("Writes the change against it")
    delta, good = (None, None) if before is None else _change(tile, value - before)
    # log.debug("Returns the row")
    return TileRow(
        measure=tile.column, label=tile.label, value=tile.value(value), delta=delta, good=good
    )


# log.debug("Defines how a measure is read from a run's row")
def _measure(row: pd.Series[Any] | None = None, column: str | None = None) -> float:
    """Returns the measure as a number, a missing one as zero.

    Args:
        row: A run's row of the runs table. Required.
        column: The measure's column. Required.

    Returns:
        The value; zero when the summary had none.
    """
    # log.debug("Takes the row, which the caller must give")
    row = required(row=row)
    # log.debug("Takes the column, which the caller must give")
    column = required(column=column)
    # log.debug("Returns zero for a missing measure, else the value as a number")
    return 0.0 if pd.isna(row[column]) else float(row[column])


# log.debug("Defines how a change is written and judged")
def _change(tile: Tile | None = None, diff: float | None = None) -> tuple[str, bool | None]:
    """Returns the change as written, and whether it is for the better.

    A change that rounds to nothing has no direction and is neither
    good nor bad.

    Args:
        tile: The tile. Required.
        diff: The run in focus's value less the earlier run's.
            Required.

    Returns:
        The change as written, and True for the better, False for the
        worse, or None for no change.
    """
    # log.debug("Takes the tile, which the caller must give")
    tile = required(tile=tile)
    # log.debug("Takes the difference, which the caller must give")
    diff = required(diff=diff)
    # log.debug("Writes the size of the change as the tile writes it")
    shown = (tile.change or tile.value)(abs(diff))
    # log.debug("Calls a change that rounds to nothing no change")
    if abs(diff) < TINY or not any(digit in NONZERO_DIGITS for digit in shown):
        # log.debug("Returns no change")
        return NO_CHANGE, None
    # log.debug("Returns the direction and size, and whether that is for the better")
    return f"{UP if diff > 0 else DOWN} {shown}", (diff > 0) == (tile.better == UP)
