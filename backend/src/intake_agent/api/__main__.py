########################################################################
#               backend/src/intake_agent/api/__main__.py               #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Runs the service: python -m intake_agent.api, on the host and port in
settings.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

# Third-party
import uvicorn
from kds.logs import get_logger

# Local
from intake_agent.api.app import create_app
from intake_agent.config import get_app_settings

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)


########################################################################
#                             Entry point                              #
########################################################################
# log.debug("Defines the entry point")
def main() -> None:
    """Serves the app; the service logs each request itself."""
    # log.debug("Reads the settings once")
    settings = get_app_settings()
    # log.debug("Serves the app until stopped")
    uvicorn.run(
        create_app(settings), host=settings.api_host, port=settings.api_port, access_log=False
    )


# log.debug("Runs main when the module is run as a script")
if __name__ == "__main__":
    # log.debug("Starts the service")
    main()
