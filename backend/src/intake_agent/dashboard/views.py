########################################################################
#                                                                      #
#             backend/src/intake_agent/dashboard/views.py              #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-03
Last modified on:  2026-11-03

Picks out of the run tables what the dashboard's views show: the runs
a chart can draw, each run's long label, the kinds of scenario in the
order the results report them, the scenarios that did not end as
expected written as a person would write them, and any table's rows as
Dash's tables take them.
"""

########################################################################
#                                                                      #
#                               Imports                                #
#                                                                      #
########################################################################
# Standard library
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

# Third-party
import pandas as pd
from kds.args import missing, required
from kds.logs import get_logger

# Local
from intake_agent.config import SETTINGS

########################################################################
#                                                                      #
#                           Global constants                           #
#                                                                      #
########################################################################
log = get_logger(__name__)
# log.debug("Takes the run id column, from the config")
RUN_ID: Final = SETTINGS.columns_run_id
# log.debug("Takes the column of each run's long label, from the config")
RUN: Final = SETTINGS.columns_run
# log.debug("Takes the kind of scenario column, from the config")
CATEGORY: Final = SETTINGS.columns_category
# log.debug("Takes the column that is 1 when a scenario ended as expected, from the config")
AS_EXPECTED: Final = SETTINGS.columns_as_expected
# log.debug("Takes the name of each kind of scenario, in order, from the config")
CATEGORY_LABELS: Final = SETTINGS.labels_categories
# log.debug("Takes the most runs a chart compares, from the config")
MAX_RUNS: Final = SETTINGS.charts_max_runs

########################################################################
#                                                                      #
#                           Local constants                            #
#                                                                      #
########################################################################
# log.debug("Describes a table row as Dash's tables take it: values by column name")
Record = dict[str | float | int, Any]
# log.debug("Lists the columns of the wrong-scenarios table that hold a verdict")
VERDICTS: Final = ("expected_recommendation", "recommendation", "agent_recommendation")
# log.debug("Sets the words for a scenario that ended with no draft, so no verdict")
NO_DRAFT: Final = "no draft"
# log.debug("Names the column that says whether a failure scenario was handled")
HANDLED: Final = "handled"
# log.debug("Names the column of the planted records the findings included")
FOUND: Final = "found"
# log.debug("Names the column of the planted records there were")
PLANTED: Final = "planted"
# log.debug("Sets the word a yes is shown as")
YES: Final = "Yes"
# log.debug("Sets the word a no is shown as")
NO: Final = "No"


########################################################################
#                                                                      #
#                           Dashboard views                            #
#                                                                      #
########################################################################
# log.debug("Defines which of the runs asked for a table holds")
def present(
    frame: pd.DataFrame | None = None, run_ids: str | Sequence[str] | None = None
) -> list[str]:
    """Returns the runs asked for that the table holds, at most three.

    Args:
        frame: Any of the three tables. Required.
        run_ids: One run id, or several in the order picked. Required.

    Returns:
        The ids held, in the order asked, the first three only.
    """
    # log.debug("Takes the table, which the caller must give")
    frame = required(frame=frame)
    # log.debug("Stops when the caller left out the run ids")
    if run_ids is None:
        # log.debug("Raises the missing-argument error")
        raise missing(run_ids=run_ids)
    # log.debug("Treats a single id as a list of one")
    asked = [run_ids] if isinstance(run_ids, str) else list(run_ids)
    # log.debug("Lists the run ids the table holds")
    known = set(frame[RUN_ID])
    # log.debug("Returns the ids held, the first three only")
    return [r for r in asked if r in known][:MAX_RUNS]


# log.debug("Defines each run's long label, read from a table")
def long_labels(
    frame: pd.DataFrame | None = None, run_ids: Sequence[str] | None = None
) -> dict[str, str]:
    """Returns each run's long label, from its first row in the table.

    Args:
        frame: Any of the three tables. Required.
        run_ids: The runs to label, each one the table holds. Required.

    Returns:
        Each run's long label by its id.
    """
    # log.debug("Takes the table, which the caller must give")
    frame = required(frame=frame)
    # log.debug("Takes the run ids, which the caller must give")
    run_ids = required(run_ids=run_ids)
    # log.debug("Returns the run column of each run's first row")
    return {r: str(frame.loc[frame[RUN_ID] == r, RUN].iloc[0]) for r in run_ids}


# log.debug("Defines the order the kinds of scenario are listed in")
def category_order(scenarios: pd.DataFrame | None = None) -> list[str]:
    """Returns the kinds of scenario held, in the order reported.

    Args:
        scenarios: The scenarios table from `frames`, or part of it.
            Required.

    Returns:
        The names of the kinds the table holds, in the order the
        results report them.
    """
    # log.debug("Takes the scenarios, which the caller must give")
    scenarios = required(scenarios=scenarios)
    # log.debug("Lists the kinds the table holds")
    held = set(scenarios[CATEGORY])
    # log.debug("Returns them in the order the results report them")
    return [name for name in CATEGORY_LABELS.values() if name in held]


# log.debug("Defines the rows of the wrong-scenarios table")
def wrong_rows(
    scenarios: pd.DataFrame | None = None, run_ids: Sequence[str] | None = None
) -> list[Record]:
    """Returns each scenario that did not end as expected, in words.

    Args:
        scenarios: The scenarios table from `frames`. Required.
        run_ids: The runs picked. Required.

    Returns:
        One record per scenario whose ending or verdict shown differs
        from the scenario's, no draft and Yes or No written as words
        and the records found written of those planted.
    """
    # log.debug("Takes the scenarios, which the caller must give")
    scenarios = required(scenarios=scenarios)
    # log.debug("Takes the run ids, which the caller must give")
    run_ids = required(run_ids=run_ids)
    # log.debug("Keeps the scenarios of the runs picked that did not end as expected")
    wrong = scenarios[scenarios[RUN_ID].isin(run_ids) & (scenarios[AS_EXPECTED] == 0)].copy()
    # log.debug("Writes a verdict of None as no draft")
    for column in VERDICTS:
        # log.debug("Rewrites one column")
        wrong[column] = wrong[column].map(_verdict)
    # log.debug("Writes whether a failure scenario was handled as Yes or No, else leaves it")
    wrong[HANDLED] = wrong[HANDLED].map(_yes_no)
    # log.debug("Writes the planted records found of those there were")
    wrong[FOUND] = wrong[FOUND].astype(str) + " of " + wrong[PLANTED].astype(str)
    # log.debug("Returns the rows as the table takes them")
    return records(wrong)


# log.debug("Defines a table's rows as Dash's tables take them")
def records(frame: pd.DataFrame | None = None) -> list[Record]:
    """Returns each row of the table as its values by column name.

    Args:
        frame: The table. Required.

    Returns:
        Each row's values by column name, in the table's order.
    """
    # log.debug("Takes the table, which the caller must give")
    frame = required(frame=frame)
    # log.debug("Returns the rows, keyed by column name")
    return [{str(key): value for key, value in row.items()} for row in frame.to_dict("records")]


# log.debug("Defines how a verdict is written for a person")
def _verdict(value: Any = None) -> str:
    """Returns a verdict in words, a missing one as no draft.

    Args:
        value: The verdict, or None when no draft was made.

    Returns:
        The verdict, or the words no draft.
    """
    # log.debug("Returns no draft for a missing verdict, else the verdict as text")
    return NO_DRAFT if value is None or pd.isna(value) else str(value)


# log.debug("Defines how a yes or no is written for a person")
def _yes_no(value: Any = None) -> str:
    """Returns Yes or No for a boolean, and nothing for a missing one.

    Args:
        value: True, False, or None for a scenario that is not a
            failure scenario.

    Returns:
        Yes, No, or empty.
    """
    # log.debug("Returns empty for a missing value")
    if value is None or pd.isna(value):
        # log.debug("Returns nothing")
        return ""
    # log.debug("Returns Yes or No")
    return YES if value else NO
