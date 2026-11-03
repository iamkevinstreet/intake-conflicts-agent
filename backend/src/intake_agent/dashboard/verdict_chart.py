########################################################################
#                                                                      #
#         backend/src/intake_agent/dashboard/verdict_chart.py          #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-03
Last modified on:  2026-11-03

Draws the chart of how each kind of scenario ended: a row per kind,
with the number of scenarios in it, and for each run picked a bar
stacked from the scenarios that ended as expected (in the run's
colour) and those that did not (in amber). The runs' key sits above
all the charts on the page, so the chart carries no key of its own.
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
from intake_agent.dashboard.theme import THEMES, Theme, hover, shared_layout, top_down
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
# log.debug("Takes the kind of scenario column, from the config")
CATEGORY: Final = SETTINGS.columns_category
# log.debug("Takes the column that is 1 when a scenario ended as expected, from the config")
AS_EXPECTED: Final = SETTINGS.columns_as_expected
# log.debug("Takes the light scheme's name, from the config")
LIGHT: Final = SETTINGS.charts_light_scheme
# log.debug("Takes the size of chart text, from the config")
FONT_SIZE: Final = SETTINGS.charts_font_size

########################################################################
#                                                                      #
#                           Local constants                            #
#                                                                      #
########################################################################
# log.debug("Sets the height of the chart above its rows")
BASE: Final = 48
# log.debug("Sets the height of each kind's row, which holds a bar per run")
ROW: Final = 72
# log.debug("Sets the width of one run's bar, as a share of its row")
BAR_WIDTH: Final = 0.24
# log.debug("Sets the room past the longest bar, as a share of it, for its count")
HEADROOM: Final = 1.25
# log.debug("Names the count of scenarios that ended as expected, in a groupby")
SUM: Final = "sum"
# log.debug("Names the count of all scenarios, in a groupby")
COUNT: Final = "count"
# log.debug("Names the segment of scenarios that ended as expected")
AS_EXPECTED_WORDS: Final = "as expected"
# log.debug("Names the segment of scenarios that did not")
NOT_AS_EXPECTED_WORDS: Final = "not as expected"


########################################################################
#                                                                      #
#                     Endings by kind of scenario                      #
#                                                                      #
########################################################################
# log.debug("Defines the chart of endings by kind of scenario")
def fig_verdicts(
    scenarios: pd.DataFrame | None = None,
    run_ids: str | Sequence[str] | None = None,
    theme: str = LIGHT,
    labels: dict[str, str] | None = None,
) -> go.Figure:
    """Returns a bar per run on each kind: as expected, stacked on not.

    Each row names its kind and how many scenarios are in it; each bar
    carries its count of scenarios that ended as expected at its end.

    Args:
        scenarios: The scenarios table from `frames`. Required.
        run_ids: Up to three runs, the run in focus first. Required.
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
    # log.debug("Names each run, from the labels given or the table")
    names = labels or long_labels(scenarios, ids)
    # log.debug("Takes the scenarios of the runs picked")
    picked = scenarios[scenarios[RUN_ID].isin(ids)]
    # log.debug("Lists the kinds held, in the order reported")
    order = category_order(picked)
    # log.debug("Counts the scenarios of each kind, across the runs picked")
    counts = picked.groupby(CATEGORY)[SCENARIO_ID].nunique()
    # log.debug("Names each row with its kind and its count")
    rows = {kind: f"{kind} ({counts[kind]})" for kind in order}
    # log.debug("Starts an empty figure")
    fig = go.Figure()
    # log.debug("Draws each run's bars in turn")
    for index, run_id in enumerate(ids):
        # log.debug("Adds the run's two segments on every row")
        fig.add_traces(
            _segments(
                _ended(picked[picked[RUN_ID] == run_id], order, rows),
                index=index,
                label=names[run_id],
                colours=colours,
            )
        )
    # log.debug("Stacks each run's segments, lists the kinds from the top down, fits the counts")
    fig.update_layout(
        barmode="stack",
        bargap=0.2,
        yaxis=top_down(list(rows.values())),
        xaxis=dict(range=[0, max(1, int(counts.max()) if len(counts) else 1) * HEADROOM]),
    )
    # log.debug("Returns the chart in the shared layout, a row per kind")
    return shared_layout(fig, BASE + ROW * max(1, len(order)), colours)


# log.debug("Defines how one run's scenarios ended, by kind")
def _ended(
    mine: pd.DataFrame | None = None,
    order: list[str] | None = None,
    rows: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Returns, per kind, how many ended as expected and how many not.

    Args:
        mine: The run's rows of the scenarios table. Required.
        order: The kinds, in the order they are listed. Required.
        rows: Each kind's row name. Required.

    Returns:
        A table indexed by row name with a column of scenarios that
        ended as expected and one of those that did not, zero for a
        kind the run has none of.
    """
    # log.debug("Takes the run's rows, which the caller must give")
    mine = required(mine=mine)
    # log.debug("Takes the kinds, which the caller must give")
    order = required(order=order)
    # log.debug("Takes the row names, which the caller must give")
    rows = required(rows=rows)
    # log.debug("Counts, per kind, the scenarios that ended as expected and all of them")
    ended = mine.groupby(CATEGORY)[AS_EXPECTED].agg([SUM, COUNT]).reindex(order).fillna(0)
    # log.debug("Returns the two counts per kind, under the row names")
    return pd.DataFrame(
        {
            AS_EXPECTED_WORDS: ended[SUM].astype(int).to_numpy(),
            NOT_AS_EXPECTED_WORDS: (ended[COUNT] - ended[SUM]).astype(int).to_numpy(),
        },
        index=[rows[kind] for kind in order],
    )


# log.debug("Defines one run's two segments")
def _segments(
    ended: pd.DataFrame | None = None,
    *,
    index: int | None = None,
    label: str | None = None,
    colours: Theme | None = None,
) -> list[go.Bar]:
    """Returns the run's as-expected bars, and the not-as-expected ones.

    The count of scenarios that ended as expected is written at the
    end of each stack: on the top segment, whichever that is.

    Args:
        ended: The run's counts per kind, from `_ended`. Required.
        index: The run's place among those picked; 0 is in focus.
            Required.
        label: The run's name for the hover. Required.
        colours: The scheme to draw in. Required.

    Returns:
        The two bar traces, the as-expected one first.
    """
    # log.debug("Takes the counts, which the caller must give")
    ended = required(ended=ended)
    # log.debug("Takes the run's place, which the caller must give")
    index = required(index=index)
    # log.debug("Takes the label, which the caller must give")
    label = required(label=label)
    # log.debug("Takes the colours, which the caller must give")
    colours = required(colours=colours)
    # log.debug("Reads the two counts and their total per row")
    right, wrong = ended[AS_EXPECTED_WORDS], ended[NOT_AS_EXPECTED_WORDS]
    # log.debug("Writes each row's count of scenarios that ended as expected, of all of them")
    counts = [f"{r} of {r + w}" for r, w in zip(right, wrong, strict=True)]
    # log.debug("Sets what the two segments share")
    shared = dict(
        y=list(ended.index),
        orientation="h",
        offsetgroup=str(index),
        width=BAR_WIDTH,
        textposition="outside",
        textfont=dict(color=colours.ink2, size=FONT_SIZE),
        cliponaxis=False,
        customdata=counts,
    )
    # log.debug("Returns the as-expected segment, then the not-as-expected one on top of it")
    return [
        go.Bar(
            x=right,
            name=f"{label}, {AS_EXPECTED_WORDS}",
            marker=dict(color=colours.runs[index], line=dict(width=0)),
            text=[c if w == 0 else "" for c, w in zip(counts, wrong, strict=True)],
            hovertemplate=hover(f"<b>%{{customdata}}</b> {AS_EXPECTED_WORDS}  %{{y}}", label),
            meta=dict(role=f"run-{index}"),
            **shared,
        ),
        go.Bar(
            x=wrong,
            name=f"{label}, {NOT_AS_EXPECTED_WORDS}",
            marker=dict(color=colours.wrong, line=dict(width=0)),
            text=[c if w > 0 else "" for c, w in zip(counts, wrong, strict=True)],
            hovertemplate=hover(f"<b>%{{x}}</b> {NOT_AS_EXPECTED_WORDS}  %{{y}}", label),
            meta=dict(role=f"miss-{index}"),
            **shared,
        ),
    ]
