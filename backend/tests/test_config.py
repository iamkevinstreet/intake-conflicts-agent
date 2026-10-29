########################################################################
#                     backend/tests/test_config.py                     #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           Tests that config/settings.toml lists every      #
#                     default in code and holds no secret.             #
########################################################################
"""Tests that config/settings.toml lists every default and no secret."""

from __future__ import annotations

import tomllib
from typing import Any

from kds.logs import get_logger
from kds.settings.toml import flatten, is_secret

from intake_agent.config import AppSettings

from support import REPO

# Module constants
log = get_logger(__name__)


# log.debug("Defines how the repository's settings file is read")
def _file_values() -> dict[str, Any]:
    """Return config/settings.toml as flat field names and values."""
    # log.debug("Reads and flattens the file")
    return flatten(tomllib.loads((REPO / "config" / "settings.toml").read_text(encoding="utf-8")))


# log.debug("Defines the test that the file matches the code's defaults")
def test_settings_file_lists_every_default() -> None:
    """Every setting but secrets is in the file, at its default."""
    # log.debug("Reads the file")
    values = _file_values()
    # log.debug("Lists every field that is not a secret")
    fields = {n for n, f in AppSettings.model_fields.items() if not is_secret(f)}
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
    """Secret fields are never set in settings.toml."""
    # log.debug("Checks no secret field is in the file")
    assert not [n for n in _file_values() if is_secret(AppSettings.model_fields[n])]
