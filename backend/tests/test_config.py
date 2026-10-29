########################################################################
#                     backend/tests/test_config.py                     #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Tests that config/config.toml lists every default in code and holds no
secret.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

import tomllib
from typing import Any

# Third-party
from kds.logs import get_logger
from kds.settings import toml

# Local
from intake_agent.config import AppSettings
from support import REPO

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)


########################################################################
#                          Config file tests                           #
########################################################################
# log.debug("Defines how the repository's settings file is read")
def _file_values() -> dict[str, Any]:
    """Returns config/config.toml as flat field names and values.

    Returns:
        Each setting's field name mapped to its value in the file.
    """
    # log.debug("Reads and flattens the file")
    return toml.flatten(
        tomllib.loads((REPO / "config" / "config.toml").read_text(encoding="utf-8"))
    )


# log.debug("Defines the test that the file matches the code's defaults")
def test_settings_file_lists_every_default() -> None:
    """Every setting but secrets is in the file, at its default."""
    # log.debug("Reads the file")
    values = _file_values()
    # log.debug("Lists every field that is not a secret")
    fields = {n for n, f in AppSettings.model_fields.items() if not toml.is_secret(f)}
    # log.debug("Checks the file names each one except the Azure endpoint")
    assert set(values) == fields - {"azure_openai_endpoint"}
    # log.debug("Checks each value, once validated, equals the field's default")
    for name, value in values.items():
        # log.debug("Validates the value through the settings and compares")
        assert getattr(AppSettings(**{name: value}), name) == (
            AppSettings.model_fields[name].default
        ), name


# log.debug("Defines the test that the file holds no secret")
def test_settings_file_holds_no_secret() -> None:
    """Secret fields are never set in config.toml."""
    # log.debug("Checks no secret field is in the file")
    assert not [n for n in _file_values() if toml.is_secret(AppSettings.model_fields[n])]
