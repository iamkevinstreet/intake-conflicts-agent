########################################################################
#                                                                      #
#              backend/src/intake_agent/dashboard/app.py               #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-03
Last modified on:  2026-11-03

Builds the Dash app from the results folder and redraws it for the
runs picked: the runs' key, the tiles, the four charts and the
wrong-scenarios table. The first run picked is the one in focus. The
charts need real colours, so the browser tells the server its scheme.
"""

########################################################################
#                                                                      #
#                               Imports                                #
#                                                                      #
########################################################################
# Standard library
from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Final, cast

# Third-party
import pandas as pd
from dash import Dash, Input, Output, html
from dash.development.base_component import Component
from kds.args import required
from kds.logs import get_logger

# Local
from intake_agent.config import SETTINGS
from intake_agent.dashboard.data import frames, load_runs, run_labels
from intake_agent.dashboard.layout import page_layout
from intake_agent.dashboard.page import INDEX
from intake_agent.dashboard.run_charts import fig_cost, fig_latency
from intake_agent.dashboard.steps_chart import fig_steps
from intake_agent.dashboard.theme import THEMES
from intake_agent.dashboard.tiles import TileRow, tile_rows
from intake_agent.dashboard.verdict_chart import fig_verdicts
from intake_agent.dashboard.views import wrong_rows

########################################################################
#                                                                      #
#                           Global constants                           #
#                                                                      #
########################################################################
log = get_logger(__name__)
# log.debug("Takes the run id column, from the config")
RUN_ID: Final = SETTINGS.columns_run_id
# log.debug("Takes the location's id, whose first change reads the scheme, from the config")
URL_ID: Final = SETTINGS.dashboard_ids_url
# log.debug("Takes the id of the store that holds the colour scheme, from the config")
SCHEME_ID: Final = SETTINGS.dashboard_ids_scheme
# log.debug("Takes the run picker's id, from the config")
RUNS_ID: Final = SETTINGS.dashboard_ids_runs
# log.debug("Takes the id of the runs' key, from the config")
LEGEND_ID: Final = SETTINGS.dashboard_ids_legend
# log.debug("Takes the tiles' id, from the config")
TILES_ID: Final = SETTINGS.dashboard_ids_tiles
# log.debug("Takes the id of the chart of endings by kind, from the config")
VERDICTS_ID: Final = SETTINGS.dashboard_ids_verdicts
# log.debug("Takes the id of the chart of work per scenario, from the config")
STEPS_ID: Final = SETTINGS.dashboard_ids_steps
# log.debug("Takes the time chart's id, from the config")
LATENCY_ID: Final = SETTINGS.dashboard_ids_latency
# log.debug("Takes the cost chart's id, from the config")
COST_ID: Final = SETTINGS.dashboard_ids_cost
# log.debug("Takes the wrong-scenarios table's id, from the config")
WRONG_TABLE_ID: Final = SETTINGS.dashboard_ids_wrong_table
# log.debug("Takes the light scheme's name, the one used before the browser says, from the config")
LIGHT: Final = SETTINGS.charts_light_scheme
# log.debug("Takes the most runs a chart compares, from the config")
MAX_RUNS: Final = SETTINGS.charts_max_runs

########################################################################
#                                                                      #
#                           Local constants                            #
#                                                                      #
########################################################################
# log.debug("Sets the browser tab's title")
TITLE: Final = "New-matter intake agent: evaluation"
# log.debug("Sets the browser code that says whether the page is in dark mode")
SCHEME_JS: Final = (
    "function(_) { return window.matchMedia && "
    "window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'; }"
)
# log.debug("Names the property that holds an element's children")
CHILDREN: Final = "children"
# log.debug("Names the property that holds a chart's figure")
FIGURE: Final = "figure"
# log.debug("Names the property that holds a store's or a table's data")
DATA: Final = "data"
# log.debug("Names the picker's property that holds the runs picked")
PICKED: Final = "value"
# log.debug("Sets the style of a tile's change by whether it is for the better")
TONES: Final = {None: "flat", True: "good", False: "bad"}
# log.debug("Hides a tile's arrow from screen readers, since its words say the same")
HIDDEN: Final[dict[str, Any]] = {"aria-hidden": "true"}
# log.debug("Describes the callback: the runs picked and the scheme in, the redraw out")
Redraw = Callable[[list[str] | None, str | None], tuple[Any, ...]]


########################################################################
#                                                                      #
#                            Dashboard app                             #
#                                                                      #
########################################################################
# log.debug("Defines the app factory")
def build_app(results: Path | None = None) -> Dash:
    """Returns the dashboard over the runs in the folder.

    Args:
        results: The folder of run files, live and offline. Required.

    Returns:
        The app; `app.run` serves it.
    """
    # log.debug("Takes the results folder, which the caller must give")
    results = required(results=results)
    # log.debug("Reads the runs into the three tables")
    runs_df, scenarios_df, _ = frames(load_runs(results))
    # log.debug("Names every run for the picker")
    names = run_labels(runs_df, list(runs_df[RUN_ID]))
    # log.debug("Offers every run, newest first")
    options = [dict(label=names[r], value=r) for r in runs_df[RUN_ID]]
    # log.debug("Puts the newest run in focus when the page opens")
    default = list(runs_df[RUN_ID])[:1]
    # log.debug("Creates the app")
    app = Dash(__name__, title=TITLE)
    # log.debug("Lays out the page")
    app.layout = page_layout(runs_df, options, default)
    # Dash leaves clientside_callback without types; the cast says what
    # it is, so the strict check still covers the call.
    # log.debug("Takes Dash's registration of a callback that runs in the browser")
    in_browser = cast(Callable[..., None], app.clientside_callback)
    # log.debug("Asks the browser for its colour scheme when the page loads")
    in_browser(SCHEME_JS, Output(SCHEME_ID, DATA), Input(URL_ID, "pathname"))
    # log.debug("Redraws the key, tiles, charts and wrong scenarios when the picks or scheme move")
    app.callback(
        Output(LEGEND_ID, CHILDREN),
        Output(TILES_ID, CHILDREN),
        Output(VERDICTS_ID, FIGURE),
        Output(STEPS_ID, FIGURE),
        Output(LATENCY_ID, FIGURE),
        Output(COST_ID, FIGURE),
        Output(WRONG_TABLE_ID, DATA),
        Input(RUNS_ID, PICKED),
        Input(SCHEME_ID, DATA),
    )(_redraw(runs_df, scenarios_df, default))
    # log.debug("Serves the page in the site's fonts and colours")
    app.index_string = INDEX
    # log.debug("Returns the app")
    return app


# log.debug("Defines the callback that redraws the page for the runs picked")
def _redraw(
    runs_df: pd.DataFrame | None = None,
    scenarios_df: pd.DataFrame | None = None,
    default: list[str] | None = None,
) -> Redraw:
    """Returns the callback, which reads the tables built at startup.

    Args:
        runs_df: The runs table built at startup. Required.
        scenarios_df: The scenarios table built at startup. Required.
        default: The runs picked when the page opens, used when none
            are picked. Required.

    Returns:
        The callback, for app.callback.
    """
    # log.debug("Takes the runs table, which the caller must give")
    runs_df = required(runs_df=runs_df)
    # log.debug("Takes the scenarios table, which the caller must give")
    scenarios_df = required(scenarios_df=scenarios_df)
    # log.debug("Takes the runs picked at first, which the caller must give")
    default = required(default=default)

    # log.debug("Defines the callback")
    def redraw(  # fixed: Dash's callback signature
        selected: list[str] | None, scheme: str | None
    ) -> tuple[Any, ...]:
        """Returns the key, tiles, four charts and wrong scenarios.

        Args:
            selected: The runs picked; none puts the newest in focus.
            scheme: The browser's colour scheme; None until it says.

        Returns:
            The runs' key, the tiles, the four charts and the
            wrong-scenarios rows, in the order of the callback's
            outputs.
        """
        # log.debug("Draws in the browser's scheme, light when it is not known")
        theme = LIGHT if scheme is None or scheme not in THEMES else scheme
        # log.debug("Takes up to three of the runs picked, or the newest when none are")
        picked = (selected or default)[:MAX_RUNS]
        # log.debug("Names the runs picked")
        labels = run_labels(runs_df, picked)
        # log.debug("Returns everything the page redraws, in the order of its outputs")
        return (
            _legend(picked, labels),
            [_tile(row) for row in tile_rows(runs_df, picked)],
            fig_verdicts(scenarios_df, picked, theme, labels),
            fig_steps(scenarios_df, picked, theme, labels),
            fig_latency(scenarios_df, picked, theme, labels),
            fig_cost(runs_df, picked, theme, labels),
            wrong_rows(scenarios_df, picked),
        )

    # log.debug("Returns the callback")
    return redraw


# log.debug("Defines the runs' key")
def _legend(
    picked: Sequence[str] | None = None, labels: dict[str, str] | None = None
) -> list[html.Span]:
    """Returns a dot in each run's colour and its name, focus marked.

    Args:
        picked: The runs picked, the run in focus first. Required.
        labels: Each run's short name. Required.

    Returns:
        A key per run: a dot in its colour and its name, the first
        marked as in focus.
    """
    # log.debug("Takes the runs picked, which the caller must give")
    picked = required(picked=picked)
    # log.debug("Takes the labels, which the caller must give")
    labels = required(labels=labels)
    # log.debug("Returns one key per run, the first marked as in focus")
    return [
        html.Span(
            className="key",
            children=[
                html.Span(className=f"dot run-{i}"),
                labels[run_id] + (" (in focus)" if i == 0 else ""),
            ],
        )
        for i, run_id in enumerate(picked)
    ]


# log.debug("Defines one tile")
def _tile(row: TileRow | None = None) -> html.Div:
    """Returns a tile: its value, its label, and its change if any.

    Args:
        row: The tile's row, from tile_rows. Required.

    Returns:
        The tile.
    """
    # log.debug("Takes the row, which the caller must give")
    row = required(row=row)
    # log.debug("Starts with the value over the label")
    children: list[Component | str] = [
        html.Div(row["value"], className="tile-value"),
        html.Div(row["label"], className="tile-label"),
    ]
    # log.debug("Reads the change")
    delta = row["delta"]
    # log.debug("Adds the change with its arrow, when there is one")
    if delta:
        # log.debug("Takes the direction from the first word: up, down or no")
        way = delta.split(" ")[0]
        # log.debug("Adds the change, coloured by whether it is for the better")
        children.append(
            html.Div(
                className=f"tile-delta {TONES[row['good']]}",
                children=[html.Span(className=f"arrow {way}", **HIDDEN), delta],
            )
        )
    # log.debug("Returns the tile")
    return html.Div(className="tile", children=children)
