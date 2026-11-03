########################################################################
#                                                                      #
#            backend/src/intake_agent/dashboard/__main__.py            #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-03
Last modified on:  2026-11-03

Serves the dashboard, or writes the figures the case study draws.

    python -m intake_agent.dashboard
    python -m intake_agent.dashboard --export-figures [PATH]

The first serves the app on [dashboard] host and port, over the live
and offline runs in [data] results. The second writes the Plotly JSON
of the latest live runs to PATH, by default figures.json in [data]
results, and exits.
"""

########################################################################
#                                                                      #
#                               Imports                                #
#                                                                      #
########################################################################
# Standard library
from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Final

# Third-party
from kds.logs import get_logger, log_event, setup_logging
from kds.settings import describe

# Local
from intake_agent.config import SETTINGS, get_app_settings
from intake_agent.dashboard.app import build_app
from intake_agent.dashboard.export import export_figures

########################################################################
#                                                                      #
#                           Global constants                           #
#                                                                      #
########################################################################
log = get_logger(__name__)
# log.debug("Takes the name of the figures file the case study reads, from the config")
FIGURES: Final = SETTINGS.data_figures


########################################################################
#                                                                      #
#                             Command line                             #
#                                                                      #
########################################################################
# log.debug("Defines the command line")
def main(argv: Sequence[str] | None = None) -> int:
    """Serves the app until stopped, or writes the figures and returns.

    Args:
        argv: The command's arguments; the process's own when None.

    Returns:
        The exit status: 0 once the figures are written or the server
        stops.

    Raises:
        SystemExit: When there are no live runs to draw the figures of.
    """
    # log.debug("Reads the settings once")
    settings = get_app_settings()
    # log.debug("Sets up logging, and the trace lines when they are on")
    setup_logging(settings)
    # log.debug("Describes the arguments")
    parser = argparse.ArgumentParser(
        prog="python -m intake_agent.dashboard", description="Serve the evaluation dashboard."
    )
    # log.debug("Adds the figures option, which writes beside the runs without a path")
    parser.add_argument(
        "--export-figures",
        nargs="?",
        const=settings.data_results / FIGURES,
        type=Path,
        metavar="PATH",
        help="write Plotly JSON for the site and exit",
    )
    # log.debug("Reads the arguments")
    args = parser.parse_args(argv)
    # log.debug("Writes the figures and stops, when asked to")
    if args.export_figures is not None:
        # log.debug("Writes them, and turns having no live runs into a message and status 1")
        try:
            # log.debug("Writes the figures")
            payload = export_figures(settings.data_results, args.export_figures)
        except FileNotFoundError as error:
            # log.debug("Exits with the message")
            raise SystemExit(str(error)) from error
        # log.debug("Counts the figures written")
        count = len(payload["figures"])
        # log.debug("Says what was written")
        print(f"wrote {args.export_figures} ({count} figures for {payload['run_id']})")
        # log.debug("Returns success")
        return 0
    # log.debug("Logs the start and every setting, secrets masked")
    log_event(log, "dashboard.start", settings=describe(settings))
    # log.debug("Serves the app until stopped, without the debugger")
    build_app(settings.data_results).run(
        host=settings.dashboard_host, port=settings.dashboard_port, debug=False
    )
    # log.debug("Returns success once the server stops")
    return 0


# log.debug("Runs main when the module is run as a script")
if __name__ == "__main__":
    # log.debug("Exits with main's status")
    raise SystemExit(main())
