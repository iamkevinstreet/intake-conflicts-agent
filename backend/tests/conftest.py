########################################################################
#                      backend/tests/conftest.py                       #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Gives every test its isolation and the fixtures most tests share: each
test runs offline in an empty folder, with fresh settings, and may ask
for settings that write to its temporary folder and a seeded firm.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

# Third-party
import pytest
from kds.logs import get_logger
from kds.settings import get_settings

# Local
from intake_agent.config import AppSettings, get_app_settings
from intake_agent.core.store import Store
from support import REPO, seeded_store

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)


########################################################################
#                            Test isolation                            #
########################################################################
# log.debug("Defines the isolation every test gets")
@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Runs in an empty folder, offline, with no cached settings.

    Args:
        tmp_path: A temporary folder pytest makes for this test.
        monkeypatch: pytest's helper for patching the environment and
            objects.

    Yields:
        Nothing; the test runs while the fixture waits here.
    """
    # log.debug("Moves into an empty folder, so no config/.env or config.toml is read")
    monkeypatch.chdir(tmp_path)
    # log.debug("Forces the offline provider")
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    # log.debug("Sends logs to the temporary folder")
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    # log.debug("Clears the cached shared settings")
    get_settings.cache_clear()
    # log.debug("Clears the cached service settings")
    get_app_settings.cache_clear()
    # log.debug("Runs the test")
    yield
    # log.debug("Clears the caches again for the next test")
    get_app_settings.cache_clear()


# log.debug("Defines the settings most tests use")
@pytest.fixture
def settings(tmp_path: Path) -> AppSettings:
    """Settings that read the repository's data, write to tmp_path.

    Args:
        tmp_path: A temporary folder pytest makes for this test.

    Returns:
        The defaults, with the firm database, results and logs in the
        temporary folder.
    """
    # log.debug("Returns them")
    return AppSettings(
        data_firm=REPO / "data/samples/firm.json",
        data_scenarios=REPO / "data/evals/scenarios.jsonl",
        data_database=tmp_path / "firm.sqlite",
        data_results=tmp_path / "results",
        log_dir=tmp_path / "logs",
    )


# log.debug("Defines a seeded firm database")
@pytest.fixture
def store(settings: AppSettings) -> Store:
    """A firm database built from the planted records and the seed.

    Args:
        settings: The test's settings, which put the database in its
            temporary folder.

    Returns:
        The seeded database.
    """
    # log.debug("Returns it")
    return seeded_store(settings)
