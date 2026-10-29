########################################################################
#               backend/src/intake_agent/core/planted.py               #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Reads data/samples/firm.json: the clients and matters the evaluation's
scenarios are written around, and the names the scenarios use for
parties the firm never met. The file is validated before anything uses
it, so a matter cannot name a client the file does not plant.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

import json
from pathlib import Path
from typing import Self

# Third-party
from kds.args import required
from kds.logs import get_logger
from pydantic import BaseModel, Field, model_validator

# Local
from intake_agent.core.firm import ClientStatus, MatterStatus

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)

########################################################################
#                           Local constants                            #
########################################################################
# log.debug("Matches a matter number")
MATTER_NUMBER = r"^M-\d{4}$"


########################################################################
#                         Planted-records file                         #
########################################################################
# log.debug("Defines a planted client")
class PlantedClient(BaseModel):
    """A client the scenarios are written around."""

    # log.debug("Holds the name")
    name: str = Field(min_length=1)
    # log.debug("Holds current or former")
    status: ClientStatus


# log.debug("Defines a planted matter")
class PlantedMatter(BaseModel):
    """A matter the scenarios are written around, with its parties."""

    # log.debug("Holds the matter number")
    number: str = Field(pattern=MATTER_NUMBER)
    # log.debug("Holds the client's name, one of the planted clients")
    client: str
    # log.debug("Holds the kind of matter")
    kind: str
    # log.debug("Holds open or closed")
    status: MatterStatus
    # log.debug("Holds the parties the firm is against in it")
    adverse: list[str]


# log.debug("Defines the planted-records file")
class FirmFile(BaseModel):
    """data/samples/firm.json: planted records and reserved names."""

    # log.debug("Holds the file's own description")
    about: str
    # log.debug("Holds the planted clients")
    clients: list[PlantedClient]
    # log.debug("Holds the planted matters")
    matters: list[PlantedMatter]
    # log.debug("Holds names the scenarios use for parties the firm never met")
    reserved: list[str]

    # log.debug("Defines the check that every matter's client is planted")
    @model_validator(mode="after")
    def _clients_exist(self) -> Self:
        """Refuses a matter whose client is not in the clients list.

        Returns:
            The file, unchanged, when every matter's client is planted.

        Raises:
            ValueError: A matter names a client the file does not
                plant.
        """
        # log.debug("Collects the planted client names")
        names = {client.name for client in self.clients}
        # log.debug("Finds matters whose client is missing")
        missing = [m.number for m in self.matters if m.client not in names]
        # log.debug("Refuses the file when any are missing")
        if missing:
            # log.debug("Raises, naming the matters")
            msg = f"matters with an unknown client: {', '.join(missing)}"
            # log.debug("Raises the refusal")
            raise ValueError(msg)
        # log.debug("Returns the file")
        return self

    # log.debug("Defines every name the generator must keep clear of")
    def protected(self) -> list[str]:
        """Returns every planted and reserved name.

        Returns:
            The planted clients, then every planted matter's adverse
            parties, then the reserved names.
        """
        # log.debug("Collects clients, adverse parties and reserved names")
        return [
            *(client.name for client in self.clients),
            *(name for matter in self.matters for name in matter.adverse),
            *self.reserved,
        ]


# log.debug("Defines how the planted-records file is read")
def load_firm(path: Path | None = None) -> FirmFile:
    """Returns the planted records, validated.

    Args:
        path: The planted-records file, data/samples/firm.json by
            default in settings. Required.

    Returns:
        The file's clients, matters and reserved names.
    """
    # log.debug("Takes the path, which the caller must give")
    path = required(path=path)
    # log.debug("Parses and validates the file")
    return FirmFile.model_validate(json.loads(path.read_text(encoding="utf-8")))
