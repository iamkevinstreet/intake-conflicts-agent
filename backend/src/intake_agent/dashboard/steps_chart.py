########################################################################
#                                                                      #
#          backend/src/intake_agent/dashboard/steps_chart.py           #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-03
Last modified on:  2026-11-03

Draws the chart of how much work each scenario took in the run in
focus: a row per scenario, grouped by kind on a two-level axis, with a
bar for its model calls and one for its tool calls. The chart carries
its own key, since the two bars are measures, not runs.
"""

########################################################################
#                                                                      #
#                               Imports                                #
#                                                                      #
########################################################################
# Standard library
from __future__ import annotations

from collections.abc import Sequence
from typing import Final

# Third-party
import pandas as pd
import plotly.graph_objects as go
from kds.args import missing, required
from kds.logs import get_logger

# Local
from intake_agent.config import SETTINGS
from intake_agent.dashboard.theme import THEMES, hover, shared_layout
from intake_agent.dashboard.views import category_order, long_labels, present

########################################################################
#                                                                      #
#                           Global constants                           #
#                                                                      #
########################################################################
log = get_logger(__name__)
# log.debug("Takes the run id column, from the config")
RUN_ID: Final = SETTINGS.columns_run_id
# log.debug("Takes the scenario id column, from the config")
SCENARIO_ID: Final = SETTINGS.columns_scenario_id
# log.debug("Takes the scenario title column, from the config")
TITLE: Final = SETTINGS.columns_title
# log.debug("Takes the kind of scenario column, from the config")
CATEGORY: Final = SETTINGS.columns_category
# log.debug("Takes the column of each scenario's model calls, from the config")
STEPS: Final = SETTINGS.columns_steps
# log.debug("Takes the column of each scenario's tool calls, from the config")
TOOL_CALLS: Final = SETTINGS.columns_tool_calls
# log.debug("Takes the light scheme's name, from the config")
LIGHT: Final = SETTINGS.charts_light_scheme
# log.debug("Takes the size of value-axis ticks and small notes, from the config")
TICK_SIZE: Final = SETTINGS.charts_tick_size

########################################################################
#                                                                      #
#                           Local constants                            #
#                                                                      #
########################################################################
# log.debug("Sets the height of the chart above its rows, with room for the key")
BASE: Final = 72
# log.debug("Sets the height of each scenario's row")
ROW: Final = 26
# log.debug("Sets the height of the chart when no run picked is held")
EMPTY_HEIGHT: Final = 200
# log.debug("Sets the gap between rows, as a share of a row")
ROW_GAP: Final = 0.3
# log.debug("Sets the words for the model calls")
MODEL_CALLS: Final = "model calls"
# log.debug("Sets the words for the tool calls")
TOOL_CALLS_WORDS: Final = "tool calls"
# log.debug("Sets the run ramp step the tool calls are drawn in, lighter than the model calls")
TOOL_STEP: Final = 2
# log.debug("Names the column that ranks each kind while the rows are sorted")
RANK: Final = "_rank"


########################################################################
#                                                                      #
#                          Work per scenario                           #
#                                                                      #
########################################################################
# log.debug("Defines the chart of model calls and tool calls per scenario")
def fig_steps(
    scenarios: pd.DataFrame | None = None,
    run_ids: str | Sequence[str] | None = None,
    theme: str = LIGHT,
    labels: dict[str, str] | None = None,
) -> go.Figure:
    """Returns a row per scenario of the run in focus, grouped by kind.

    Each row has a bar for the scenario's model calls and one for its
    tool calls; the hover names the scenario.

    Args:
        scenarios: The scenarios table from `frames`. Required.
        run_ids: Up to three runs, the run in focus first; only the
            run in focus is drawn. Required.
        theme: The colour scheme, light or dark.
        labels: Each run's name for the hover; long labels when None.

    Returns:
        The chart.
    """
    # log.debug("Takes the scenarios, which the caller must give")
    scenarios = required(scenarios=scenarios)
    # log.debug("Stops when the caller left out the run ids")
    if run_ids is None:
        # log.debug("Raises the missing-argument error")
        raise missing(run_ids=run_ids)
    # log.debug("Takes the scheme's colours")
    colours = THEMES[theme]
    # log.debug("Keeps the runs the table holds, at most three")
    ids = present(scenarios, run_ids)
    # log.debug("Draws an empty chart when the table holds none of them")
    if not ids:
        # log.debug("Returns the empty chart")
        return shared_layout(go.Figure(), EMPTY_HEIGHT, colours)
    # log.debug("Names the run in focus, from the labels given or the table")
    label = (labels or long_labels(scenarios, ids))[ids[0]]
    # log.debug("Takes the run in focus's scenarios, grouped by kind and in id order")
    mine = _in_order(scenarios[scenarios[RUN_ID] == ids[0]])
    # log.debug("Draws the two bars of every row")
    fig = go.Figure(
        [
            _bars(mine, STEPS, MODEL_CALLS, label=label, colour=colours.runs[0]),
            _bars(mine, TOOL_CALLS, TOOL_CALLS_WORDS, label=label, colour=colours.runs[TOOL_STEP]),
        ]
    )
    # log.debug("Groups the bars, lists the kinds and scenarios from the top down, fits the axis")
    fig.update_layout(
        barmode="group",
        bargap=ROW_GAP,
        yaxis=dict(autorange="reversed", dividercolor=colours.grid, showdividers=True),
        xaxis=dict(rangemode="tozero"),
    )
    # log.debug("Applies the shared layout, a row per scenario")
    fig = shared_layout(fig, BASE + ROW * len(mine), colours)
    # log.debug("Shows the key, since the two bars are measures and not runs")
    fig.update_layout(showlegend=True, margin=dict(t=32))
    # log.debug("Returns the chart")
    return fig


# log.debug("Defines the order the scenarios are listed in")
def _in_order(mine: pd.DataFrame | None = None) -> pd.DataFrame:
    """Returns the run's scenarios grouped by kind, each in id order.

    Args:
        mine: The run's rows of the scenarios table. Required.

    Returns:
        The same rows, the kinds in the order the results report them
        and the scenarios by id within each.
    """
    # log.debug("Takes the run's rows, which the caller must give")
    mine = required(mine=mine)
    # log.debug("Ranks each kind by the order the results report them")
    ranks = {kind: rank for rank, kind in enumerate(category_order(mine))}
    # log.debug("Returns the rows sorted by kind, then id")
    return mine.assign(**{RANK: mine[CATEGORY].map(ranks)}).sort_values([RANK, SCENARIO_ID])


# log.debug("Defines one measure's bars")
def _bars(
    mine: pd.DataFrame | None = None,
    column: str | None = None,
    words: str | None = None,
    *,
    label: str | None = None,
    colour: str | None = None,
) -> go.Bar:
    """Returns a bar per scenario for one measure, on two levels.

    Args:
        mine: The run's scenarios, in the order to list them. Required.
        column: The column to draw: model calls or tool calls.
            Required.
        words: What the measure is called, in the key and the hover.
            Required.
        label: The run's name for the hover. Required.
        colour: The bars' colour. Required.

    Returns:
        The bars, each row named by its kind and its scenario id.
    """
    # log.debug("Takes the run's scenarios, which the caller must give")
    mine = required(mine=mine)
    # log.debug("Takes the column, which the caller must give")
    column = required(column=column)
    # log.debug("Takes the measure's words, which the caller must give")
    words = required(words=words)
    # log.debug("Takes the label, which the caller must give")
    label = required(label=label)
    # log.debug("Takes the colour, which the caller must give")
    colour = required(colour=colour)
    # log.debug("Returns the bars, the kind as the outer level and the id as the inner")
    return go.Bar(
        x=mine[column],
        y=[mine[CATEGORY].tolist(), mine[SCENARIO_ID].tolist()],
        name=words.capitalize(),
        orientation="h",
        marker=dict(color=colour, line=dict(width=0), cornerradius=2),
        text=mine[SCENARIO_ID] + "  " + mine[TITLE],
        textposition="none",
        hovertemplate=hover(f"<b>%{{x}} {words}</b>  %{{text}}", label),
        meta=dict(role=column),
    )
