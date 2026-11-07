########################################################################
#                                                                      #
#           backend/src/intake_agent/mcp_server/__main__.py            #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-07
Last modified on:  2026-11-07

Serves the intake agent's tools to an MCP client over stdio:

    uv run --project backend python -m intake_agent.mcp_server

The client acts as the configured requester, on the same database as the
web app, where an approver decides each draft it sends. Runs still open
when the client disconnects are ended as incomplete.
"""

########################################################################
#                                                                      #
#                               Imports                                #
#                                                                      #
########################################################################
# Standard library
from __future__ import annotations

from typing import Final

# Third-party
from kds.logs import flush_spans, get_logger, log_event, setup_logging, setup_spans

# Local
from intake_agent import __version__
from intake_agent.api.state import open_records
from intake_agent.config import get_app_settings
from intake_agent.mcp_server.runs import McpRuns
from intake_agent.mcp_server.server import build_server

########################################################################
#                                                                      #
#                           Global constants                           #
#                                                                      #
########################################################################
log = get_logger(__name__)

########################################################################
#                                                                      #
#                           Local constants                            #
#                                                                      #
########################################################################
# log.debug("Names the transport a client that starts the server uses")
STDIO: Final = "stdio"


########################################################################
#                                                                      #
#                           MCP entry point                            #
#                                                                      #
########################################################################
# log.debug("Defines the entry point")
def main() -> None:
    """Opens the records once and serves the tools over stdio."""
    # log.debug("Reads the settings once")
    settings = get_app_settings()
    # log.debug("Sets up JSON logging, to stderr and the day's file")
    setup_logging(settings)
    # log.debug("Turns spans on, when they have somewhere to go")
    setup_spans(settings, service=settings.spans_service, version=__version__)
    # log.debug("Opens the database the web app uses, and the runs the client opens")
    runs = McpRuns(open_records(settings), settings)
    # log.debug("Logs that the server is starting, and over what")
    log_event(log, "mcp.start", version=__version__, transport=STDIO)
    # log.debug("Serves until the client closes the connection")
    try:
        # log.debug("Runs the server over stdio")
        build_server(runs).run(STDIO)
    finally:
        # log.debug("Ends the runs the client left open")
        log_event(log, "mcp.stop", closed=runs.close_all())
        # log.debug("Sends any spans still waiting")
        flush_spans()


# log.debug("Runs main when the module is run as a script")
if __name__ == "__main__":
    # log.debug("Starts the server")
    main()
