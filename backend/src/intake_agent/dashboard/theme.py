########################################################################
#                                                                      #
#             backend/src/intake_agent/dashboard/theme.py              #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-03
Last modified on:  2026-11-03

Sets the look every chart shares: the fonts, the colours of the light
and dark schemes, the layout and the hover. It follows the design of
kevindstreet.com (Geist, a near-black or paper ground, one yellow
highlight, green for right and amber for wrong), so the dashboard and
the case study read as one product.
"""

########################################################################
#                                                                      #
#                               Imports                                #
#                                                                      #
########################################################################
# Standard library
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

# Third-party
import plotly.graph_objects as go
from kds.args import required
from kds.logs import get_logger

# Local
from intake_agent.config import SETTINGS
from intake_agent.evals.shares import fixed

########################################################################
#                                                                      #
#                           Global constants                           #
#                                                                      #
########################################################################
log = get_logger(__name__)
# log.debug("Takes the light scheme's name, the one the export uses, from the config")
LIGHT: Final = SETTINGS.charts_light_scheme
# log.debug("Takes the dark scheme's name, from the config")
DARK: Final = SETTINGS.charts_dark_scheme
# log.debug("Takes the size of chart text, from the config")
FONT_SIZE: Final = SETTINGS.charts_font_size
# log.debug("Takes the size of value-axis ticks and small notes, from the config")
TICK_SIZE: Final = SETTINGS.charts_tick_size
# log.debug("Takes the margin every chart keeps at its edges, from the config")
EDGE: Final = SETTINGS.charts_edge
# log.debug("Takes the colour that lets the card show through, from the config")
CLEAR: Final = SETTINGS.charts_clear
# log.debug("Takes the edge titles and notes line up on, from the config")
LEFT: Final = SETTINGS.charts_align
# log.debug("Takes the decimals a cost is written with, from the config")
COST_PLACES: Final = SETTINGS.charts_cost_places

########################################################################
#                                                                      #
#                           Local constants                            #
#                                                                      #
########################################################################
# log.debug("Sets the font stack of kevindstreet.com")
FONT: Final = (
    "Geist, 'Geist Variable', ui-sans-serif, system-ui, 'Helvetica Neue', Arial, sans-serif"
)


########################################################################
#                                                                      #
#                             Chart theme                              #
#                                                                      #
########################################################################
# log.debug("Defines the colours of one scheme")
@dataclass(frozen=True)
class Theme:
    """The colours the charts use in one scheme, from kevindstreet.com.

    Runs are an ordered ramp: the run in focus in full ink, earlier
    runs in lighter steps of the same gray (monotone, visible steps,
    the light end clear of the surface). Right is the green the site
    uses, and wrong the amber it uses for a change for the worse.
    """

    # log.debug("Holds the card background")
    surface: str
    # log.debug("Holds the raised background, for hover labels and empty cells")
    surface2: str
    # log.debug("Holds the main text colour")
    ink: str
    # log.debug("Holds the secondary text colour")
    ink2: str
    # log.debug("Holds the faint text colour, for value-axis ticks")
    ink3: str
    # log.debug("Holds the grid line colour")
    grid: str
    # log.debug("Holds the rule colour, for borders and the lines joining dots")
    rule: str
    # log.debug("Holds the pale highlight behind rows that changed")
    mark_wash: str
    # log.debug("Holds the green for right")
    right: str
    # log.debug("Holds the amber for wrong: a scenario that did not end as expected")
    wrong: str
    # log.debug("Holds the run ramp, the run in focus first")
    runs: tuple[str, str, str]


# log.debug("Sets the two schemes by name")
THEMES: Final = {
    LIGHT: Theme(
        surface="#ffffff",
        surface2="#ecece8",
        ink="#111214",
        ink2="#585d66",
        ink3="#868c96",
        grid="rgba(17,18,20,0.08)",
        rule="rgba(17,18,20,0.20)",
        mark_wash="rgba(255,228,92,0.42)",
        right="#13794a",
        wrong="#b5641a",
        runs=("#111214", "#80868f", "#a7acb4"),
    ),
    DARK: Theme(
        surface="#121419",
        surface2="#1a1d24",
        ink="#f2f3f5",
        ink2="#9aa1ac",
        ink3="#6e7581",
        grid="rgba(255,255,255,0.07)",
        rule="rgba(255,255,255,0.22)",
        mark_wash="rgba(243,207,74,0.14)",
        right="#5dd39e",
        wrong="#f0b14c",
        runs=("#f2f3f5", "#7d8490", "#4a505b"),
    ),
}


# log.debug("Defines the layout every chart shares")
def shared_layout(
    fig: go.Figure | None = None, height: int | None = None, colours: Theme | None = None
) -> go.Figure:
    """Returns the figure in the shared fonts, margins, axes and hover.

    Args:
        fig: The chart, with its traces and its own axis settings.
            Required.
        height: The chart's height in pixels. Required.
        colours: The scheme to draw in. Required.

    Returns:
        The same figure, restyled.
    """
    # log.debug("Takes the figure, which the caller must give")
    fig = required(fig=fig)
    # log.debug("Takes the height, which the caller must give")
    height = required(height=height)
    # log.debug("Takes the colours, which the caller must give")
    colours = required(colours=colours)
    # log.debug("Sets the font, margins, clear backgrounds, the hidden legend and the hover")
    fig.update_layout(
        template="none",
        height=height,
        margin=dict(l=EDGE, r=12, t=EDGE, b=EDGE),
        font=dict(family=FONT, size=FONT_SIZE, color=colours.ink2),
        paper_bgcolor=CLEAR,
        plot_bgcolor=CLEAR,
        showlegend=False,
        legend=dict(
            orientation="h",
            x=0,
            xanchor=LEFT,
            y=1.0,
            yanchor="bottom",
            font=dict(color=colours.ink2, size=FONT_SIZE),
            bgcolor=CLEAR,
            itemclick="toggleothers",
        ),
        hoverlabel=dict(
            bgcolor=colours.surface2,
            bordercolor=colours.rule,
            font=dict(family=FONT, color=colours.ink, size=FONT_SIZE),
        ),
        hovermode="closest",
    )
    # log.debug("Gives the value axis a faint grid and no line or ticks")
    fig.update_xaxes(
        automargin=True,
        showgrid=True,
        gridcolor=colours.grid,
        gridwidth=1,
        zeroline=False,
        showline=False,
        ticks="",
        tickfont=dict(color=colours.ink3, size=TICK_SIZE),
    )
    # log.debug("Gives the category axis no grid, line or ticks, and room beside its labels")
    fig.update_yaxes(
        automargin=True,
        showgrid=False,
        zeroline=False,
        showline=False,
        ticks="",
        ticklabelstandoff=10,
        tickfont=dict(color=colours.ink2, size=FONT_SIZE),
    )
    # log.debug("Returns the figure")
    return fig


# log.debug("Defines the axis settings that list categories from the top down")
def top_down(categories: Sequence[str] | None = None) -> dict[str, Any]:
    """Returns axis settings that list categories in order, top first.

    The order is set here, not left to the order traces name them.

    Args:
        categories: The categories in the order to show them, top
            first. Required.

    Returns:
        The axis settings, with the order fixed and the first at the
        top.
    """
    # log.debug("Takes the categories, which the caller must give")
    categories = required(categories=categories)
    # log.debug("Returns the fixed order, reversed so the first is at the top")
    return dict(categoryorder="array", categoryarray=list(categories), autorange="reversed")


# log.debug("Defines a hover template that names the run")
def hover(text: str | None = None, label: str | None = None) -> str:
    """Returns a hover template: the text, and the run's label.

    Args:
        text: What the hover box says, with Plotly's placeholders.
            Required.
        label: The run's label, shown as the trace's name. Required.

    Returns:
        The hover template.
    """
    # log.debug("Takes the text, which the caller must give")
    text = required(text=text)
    # log.debug("Takes the label, which the caller must give")
    label = required(label=label)
    # log.debug("Returns the template with the label as its trace name")
    return f"{text}<extra>{label}</extra>"


# log.debug("Defines how a cost is written")
def dollars(value: float | None = None) -> str:
    """Returns a cost in dollars, to four decimals.

    Args:
        value: The cost, in dollars. Required.

    Returns:
        The cost with a dollar sign, to four decimals.
    """
    # log.debug("Takes the cost, which the caller must give")
    value = required(value=value)
    # log.debug("Returns the dollar sign and the rounded cost")
    return f"${fixed(value, COST_PLACES)}"
