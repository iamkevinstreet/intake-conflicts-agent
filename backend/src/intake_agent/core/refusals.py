########################################################################
#                                                                      #
#              backend/src/intake_agent/core/refusals.py               #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-03
Last modified on:  2026-11-03

The refusals a draft action can meet, each a subclass of DraftError so
a caller can catch them all or one, and the fingerprint an approval is
bound to: the SHA-256 of the draft as saved, which the approval records
and the database compares with the saved draft's before a matter opens.
"""

########################################################################
#                                                                      #
#                               Imports                                #
#                                                                      #
########################################################################
# Standard library
from __future__ import annotations

import hashlib

# Third-party
from kds.args import required
from kds.logs import get_logger

# Local
from intake_agent.core.models import Draft

########################################################################
#                                                                      #
#                           Global constants                           #
#                                                                      #
########################################################################
log = get_logger(__name__)


########################################################################
#                                                                      #
#                            Draft refusals                            #
#                                                                      #
########################################################################
# log.debug("Defines the family of refusals a draft action can meet")
class DraftError(Exception):
    """A draft action was refused; the message says why."""


# log.debug("Defines the refusal for an unknown draft")
class DraftNotFoundError(DraftError, LookupError):
    """No draft has that id."""


# log.debug("Defines the refusal for an action the draft's state does not allow")
class DraftStateError(DraftError):
    """The draft is in the wrong state for this action."""


# log.debug("Defines the refusal for a caller who may not do this")
class GateError(DraftError, PermissionError):
    """The caller may not take this action on this draft."""


# log.debug("Defines the refusal for approving a flagged draft without a reason")
class ReasonRequiredError(DraftError, ValueError):
    """Approving over a flagged check needs a written reason."""


# log.debug("Defines the fingerprint an approval is bound to")
def fingerprint(draft: Draft | None = None) -> str:
    """Returns the SHA-256 of the draft's JSON, which never changes.

    Args:
        draft: The draft as saved. Required.

    Returns:
        The hash in hex, which an approval records and the database
        compares with the saved draft's.
    """
    # log.debug("Takes the draft, which the caller must give")
    draft = required(draft=draft)
    # log.debug("Hashes the draft as saved")
    return hashlib.sha256(draft.model_dump_json().encode()).hexdigest()
