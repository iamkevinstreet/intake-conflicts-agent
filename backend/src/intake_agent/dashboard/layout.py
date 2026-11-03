########################################################################
#                                                                      #
#             backend/src/intake_agent/dashboard/layout.py             #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-03
Last modified on:  2026-11-03

Lays out the dashboard's page once, when the app starts: a header, the
run picker, the runs' key, the tiles, four chart cards and two tables.
The callback in app.py fills the key, the tiles, the charts and the
wrong-scenarios table for the runs picked; the layout and the callback
take the parts' ids from the config.
"""

########################################################################
#                                                                      #
#                               Imports                                #
#                                                                      #
########################################################################
# Standard library
from __future__ import annotations

from typing import Any, Final

# Third-party
import pandas as pd
from dash import dcc, html
from dash.dash_table.DataTable import DataTable
from kds.args import required
from kds.logs import get_logger

# Local
from intake_agent.config import SETTINGS
from intake_agent.dashboard.views import records
from intake_agent.evals.shares import pct_label

########################################################################
#                                                                      #
#                           Global constants                           #
#                                                                      #
########################################################################
log = get_logger(__name__)
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
# log.debug("Takes the title of the chart of endings by kind, from the config")
VERDICTS_TITLE: Final = SETTINGS.charts_verdicts_title
# log.debug("Takes the title of the chart of work per scenario, from the config")
STEPS_TITLE: Final = SETTINGS.charts_steps_title
# log.debug("Takes the title of the time chart, from the config")
LATENCY_TITLE: Final = SETTINGS.charts_latency_title
# log.debug("Takes the title of the cost chart, from the config")
COST_TITLE: Final = SETTINGS.charts_cost_title
# log.debug("Takes the decimals a cost is written with, from the config")
COST_PLACES: Final = SETTINGS.charts_cost_places

########################################################################
#                                                                      #
#                           Local constants                            #
#                                                                      #
########################################################################
# log.debug("Names the runs table")
RUNS_TABLE_ID: Final = "runs-table"
# log.debug("Sets the style of the paragraphs under a heading")
LEDE: Final = "lede"
# log.debug("Sets the word for the runs, above the picker and the runs table")
RUNS: Final = "Runs"
# log.debug("Sets the style of every table cell")
TABLE_CELL: Final = {
    "fontFamily": "var(--font)",
    "fontSize": 13,
    "padding": "10px 12px",
    "textAlign": "left",
    "whiteSpace": "normal",
    "height": "auto",
    "backgroundColor": "var(--surface)",
    "color": "var(--ink)",
    "border": "none",
    "borderBottom": "1px solid var(--line)",
}
# log.debug("Sets the style of every table heading")
TABLE_HEADER: Final = {
    "fontWeight": 500,
    "color": "var(--ink-2)",
    "backgroundColor": "var(--surface)",
    "borderBottom": "1px solid var(--line-strong)",
}
# Number formats are d3-format specifiers, as Dash's Format helper
# writes them; the table fills in the rest of the format.
# log.debug("Sets the format of numbers shown to one decimal")
ONE: Final = DataTable.ColumnsFormat(specifier=".1f")
# log.debug("Sets the format of whole numbers, with thousands grouped")
WHOLE: Final = DataTable.ColumnsFormat(specifier=",.0f")
# log.debug("Sets the format of costs: a dollar sign and four decimals")
MONEY: Final = DataTable.ColumnsFormat(
    specifier=f"$.{COST_PLACES}f", locale=DataTable.ColumnsFormatLocale(symbol=["$", ""])
)
# log.debug("Lists the runs table's columns: id, heading, and number format if any")
RUN_COLUMNS: Final[tuple[tuple[str, str, DataTable.ColumnsFormat | None], ...]] = (
    ("run", "Run", None),
    ("scenarios", "Scenarios", WHOLE),
    ("failures", "Not as expected", WHOLE),
    ("conflict_recall", "Planted records found", None),
    ("false_positive_rate", "Clean shown as conflict", None),
    ("escalation", "Ambiguous marked review", None),
    ("failure_handling", "Failures handled", None),
    ("opened_without_approval", "Opened without approval", WHOLE),
    ("median_seconds", "Typical s", ONE),
    ("p95_seconds", "Slow-end s", ONE),
    ("mean_cost_usd", "Cost per scenario", MONEY),
)
# Shares are written as text, so a value just under 100% never shows
# as 100.0%.
# log.debug("Lists the runs table's columns that hold shares")
SHARE_COLUMNS: Final = ("conflict_recall", "false_positive_rate", "escalation", "failure_handling")
# log.debug("Lists the wrong-scenarios table's columns: id and heading")
WRONG_COLUMNS: Final = (
    ("run", "Run"),
    ("scenario_id", "Scenario"),
    ("title", "Title"),
    ("category", "Kind"),
    ("expected_outcome", "Expected ending"),
    ("outcome", "Ending"),
    ("expected_recommendation", "Expected verdict"),
    ("recommendation", "Verdict shown"),
    ("agent_recommendation", "Agent's verdict"),
    ("found", "Planted records found"),
    ("handled", "Handled"),
)


########################################################################
#                                                                      #
#                             Page layout                              #
#                                                                      #
########################################################################
# log.debug("Defines the whole page")
def page_layout(
    runs_df: pd.DataFrame | None = None,
    options: list[dict[str, str]] | None = None,
    default: list[str] | None = None,
) -> html.Div:
    """Returns the page, its parts in reading order.

    Args:
        runs_df: The runs table, shown in full in the runs table.
            Required.
        options: The picker's choices, newest run first. Required.
        default: The runs picked when the page opens. Required.

    Returns:
        The page's outermost element.
    """
    # log.debug("Takes the runs table, which the caller must give")
    runs_df = required(runs_df=runs_df)
    # log.debug("Takes the picker's choices, which the caller must give")
    options = required(options=options)
    # log.debug("Takes the runs picked at first, which the caller must give")
    default = required(default=default)
    # log.debug("Returns the page")
    return html.Div(
        className="wrap",
        children=[
            dcc.Location(id=URL_ID),
            dcc.Store(id=SCHEME_ID),
            _header(),
            _picker(options, default),
            html.Div(id=LEGEND_ID, className="legend"),
            html.Div(id=TILES_ID, className="tiles"),
            _charts(),
            html.H2(RUNS),
            _runs_table(runs_df),
            html.H2("Scenarios that did not end as expected"),
            html.P(
                "Every scenario in the selected runs whose ending or verdict shown differs "
                "from what the scenario expected. Empty when every scenario ended as expected.",
                className=LEDE,
            ),
            _wrong_table(),
        ],
    )


# log.debug("Defines the page's header")
def _header() -> html.Header:
    """Returns the eyebrow, the title and what the page shows.

    Returns:
        The page's header.
    """
    # log.debug("Returns the header")
    return html.Header(
        className="head",
        children=[
            html.P("New-matter intake agent", className="eyebrow"),
            html.H1("Evaluation runs"),
            html.P(
                "Every run sends the same twenty scenarios through the agent and scores each "
                "against what should have happened. Pick up to three runs to compare; the "
                "first one you pick is the one in focus. In an offline run, fixed rules play "
                "the agent and no model is called: it is the baseline.",
                className=LEDE,
            ),
        ],
    )


# log.debug("Defines the run picker")
def _picker(
    options: list[dict[str, str]] | None = None, default: list[str] | None = None
) -> html.Div:
    """Returns the run picker and its label.

    Args:
        options: The picker's choices, newest run first. Required.
        default: The runs picked when the page opens. Required.

    Returns:
        The picker with its label.
    """
    # log.debug("Takes the picker's choices, which the caller must give")
    options = required(options=options)
    # log.debug("Takes the runs picked at first, which the caller must give")
    default = required(default=default)
    # log.debug("Returns the picker")
    return html.Div(
        className="controls",
        children=[
            html.Label(RUNS, htmlFor=RUNS_ID),
            dcc.Dropdown(id=RUNS_ID, options=options, value=default, multi=True, clearable=False),
        ],
    )


# log.debug("Defines the grid of chart cards")
def _charts() -> html.Div:
    """Returns the four chart cards, the two by scenario full width.

    Returns:
        The grid of chart cards.
    """
    # log.debug("Returns the cards in reading order")
    return html.Div(
        className="grid",
        children=[
            _card(VERDICTS_TITLE, VERDICTS_ID, wide=True),
            _card(STEPS_TITLE, STEPS_ID, wide=True),
            _card(LATENCY_TITLE, LATENCY_ID),
            _card(COST_TITLE, COST_ID),
        ],
    )


# log.debug("Defines one chart card")
def _card(
    title: str | None = None, graph_id: str | None = None, *, wide: bool = False
) -> html.Section:
    """Returns a card with its title over an empty chart, no toolbar.

    Args:
        title: The chart's title. Required.
        graph_id: The chart's id, which the callback fills. Required.
        wide: Whether the card spans the whole grid.

    Returns:
        The card.
    """
    # log.debug("Takes the title, which the caller must give")
    title = required(title=title)
    # log.debug("Takes the chart's id, which the caller must give")
    graph_id = required(graph_id=graph_id)
    # log.debug("Returns the card, spanning the grid when wide")
    return html.Section(
        className="card wide" if wide else "card",
        children=[html.H3(title), dcc.Graph(id=graph_id, config={"displayModeBar": False})],
    )


# log.debug("Defines the runs table")
def _runs_table(runs_df: pd.DataFrame | None = None) -> DataTable:
    """Returns every run's summary, its shares written as text.

    Args:
        runs_df: The runs table from `frames`. Required.

    Returns:
        The table of runs, every row shown.
    """
    # log.debug("Takes the runs table, which the caller must give")
    runs_df = required(runs_df=runs_df)
    # log.debug("Writes each share as text, to one decimal, a missing one as empty")
    shares = {column: runs_df[column].map(_share_text) for column in SHARE_COLUMNS}
    # log.debug("Returns the table")
    return DataTable(
        id=RUNS_TABLE_ID,
        columns=[_column(column, name, number) for column, name, number in RUN_COLUMNS],
        data=records(runs_df.assign(**shares)),
        style_as_list_view=True,
        cell_selectable=False,
        style_cell=TABLE_CELL,
        style_header=TABLE_HEADER,
    )


# log.debug("Defines how a share is written in the runs table")
def _share_text(value: Any = None) -> str:
    """Returns a share to one decimal, or empty when there is none.

    Args:
        value: The share, from 0 to 1; None or NaN when the run had
            nothing to count.

    Returns:
        The share as a percent, or empty.
    """
    # log.debug("Returns empty for a missing share, else the share to one decimal")
    return "" if value is None or pd.isna(value) else pct_label(float(value), 1)


# log.debug("Defines one column of the runs table")
def _column(
    column: str | None = None,
    name: str | None = None,
    number: DataTable.ColumnsFormat | None = None,
) -> DataTable.Columns:
    """Returns a column's id, heading and any number format.

    Args:
        column: The column's id in the runs table. Required.
        name: The column's heading. Required.
        number: The column's number format; None for text.

    Returns:
        The column's settings.
    """
    # log.debug("Takes the column's id, which the caller must give")
    column = required(column=column)
    # log.debug("Takes the heading, which the caller must give")
    name = required(name=name)
    # log.debug("Returns a plain column when it has no number format")
    if number is None:
        # log.debug("Returns the id and heading")
        return DataTable.Columns(name=name, id=column)
    # log.debug("Returns a numeric column with its format")
    return DataTable.Columns(name=name, id=column, type="numeric", format=number)


# log.debug("Defines the wrong-scenarios table")
def _wrong_table() -> DataTable:
    """Returns the wrong-scenarios table; the callback fills it.

    Returns:
        The empty table, fifteen rows to a page.
    """
    # log.debug("Returns the table, fifteen rows to a page")
    return DataTable(
        id=WRONG_TABLE_ID,
        columns=[DataTable.Columns(name=name, id=column) for column, name in WRONG_COLUMNS],
        page_size=15,
        style_as_list_view=True,
        cell_selectable=False,
        style_cell=TABLE_CELL,
        style_header=TABLE_HEADER,
    )
