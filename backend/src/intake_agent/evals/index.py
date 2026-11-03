########################################################################
#                                                                      #
#               backend/src/intake_agent/evals/index.py                #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-03
Last modified on:  2026-11-03

Writes index.json, which lists the committed results so a static site
never lists a folder.

    python -m intake_agent.evals.index

The case study fetches files by name from the repository, so it needs
a list: the live run files in `[data] results`, newest first, and the
figures file beside them. The offline baseline is left out.
"""

########################################################################
#                                                                      #
#                               Imports                                #
#                                                                      #
########################################################################
# Standard library
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

# Third-party
from kds.args import required
from kds.logs import get_logger

# Local
from intake_agent.config import SETTINGS, get_app_settings
from intake_agent.dashboard.data import live, load_runs

########################################################################
#                                                                      #
#                           Global constants                           #
#                                                                      #
########################################################################
log = get_logger(__name__)
# log.debug("Takes the run id column, from the config")
RUN_ID: Final = SETTINGS.columns_run_id
# log.debug("Takes the name of the figures file the dashboard exports, from the config")
FIGURES: Final = SETTINGS.data_figures
# log.debug("Takes the encoding the index is written in, from the config")
ENCODING: Final = SETTINGS.files_encoding

########################################################################
#                                                                      #
#                           Local constants                            #
#                                                                      #
########################################################################
# log.debug("Sets the name of the index file")
INDEX: Final = "index.json"
# log.debug("Names the list of run files")
RUNS: Final = "runs"
# log.debug("Names the figures file's entry")
FIGURES_KEY: Final = "figures"


########################################################################
#                                                                      #
#                            Results index                             #
#                                                                      #
########################################################################
# log.debug("Defines the index of a results folder")
def build_index(results: Path | None = None) -> dict[str, Any]:
    """Returns the live run files, newest first, and the figures.

    Args:
        results: The folder of run files, the index and the figures.
            Required.

    Returns:
        The live run files' names, newest first, and the figures
        file's name, or None before it exists.
    """
    # log.debug("Takes the results folder, which the caller must give")
    results = required(results=results)
    # log.debug("Returns the index, naming the figures only when they exist")
    return {
        RUNS: [f"{run[RUN_ID]}.json" for run in live(load_runs(results))],
        FIGURES_KEY: FIGURES if (results / FIGURES).exists() else None,
    }


# log.debug("Defines the command line")
def main() -> None:
    """Writes `[data] results`/index.json and says what it lists."""
    # log.debug("Reads the settings")
    settings = get_app_settings()
    # log.debug("Builds the index")
    index = build_index(settings.data_results)
    # log.debug("Names the index file")
    path = settings.data_results / INDEX
    # log.debug("Writes it, with a final newline")
    path.write_text(json.dumps(index, indent=2) + "\n", encoding=ENCODING)
    # log.debug("Says what it lists")
    print(f"wrote {path}: {len(index[RUNS])} live runs")


# log.debug("Runs the command when the module is run as a script")
if __name__ == "__main__":
    # log.debug("Calls main")
    main()
