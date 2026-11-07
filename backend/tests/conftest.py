########################################################################
#                                                                      #
#                      backend/tests/conftest.py                       #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-11-07

Gives every test its isolation and the fixtures most tests share: each
test runs offline in an empty folder, with fresh settings, and may ask
for settings that write to its temporary folder and a seeded firm.
Every span is recorded in memory, never sent.
"""

########################################################################
#                                                                      #
#                               Imports                                #
#                                                                      #
########################################################################
# Standard library
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

# Third-party
import pytest
from kds.logs import get_logger
from kds.logs.spans import Stamp
from kds.logs.steps import KEEPER
from kds.settings import get_settings
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

# Local
from intake_agent.config import AppSettings, get_app_settings
from intake_agent.core.store import Store
from support import REPO, seeded_store

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
# log.debug("Holds every span the tests open, in memory")
MEMORY = InMemorySpanExporter()


########################################################################
#                                                                      #
#                            Test isolation                            #
#                                                                      #
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


# log.debug("Defines the span recorder every test in the session shares")
@pytest.fixture(scope="session", autouse=True)
def recorded() -> Iterator[None]:
    """Records every span in memory, stamped and kept as in a service.

    Yields:
        Nothing; the session runs while the fixture waits here.
    """
    # log.debug("Creates the provider every test's spans go to")
    provider = TracerProvider()
    # log.debug("Stamps each span with its request id and session")
    provider.add_span_processor(Stamp())
    # log.debug("Records each span in memory as it ends")
    provider.add_span_processor(SimpleSpanProcessor(MEMORY))
    # log.debug("Lets evaluation runs keep their spans")
    provider.add_span_processor(KEEPER)
    # log.debug("Puts it in use for the session")
    trace.set_tracer_provider(provider)
    # log.debug("Runs the session")
    yield


# log.debug("Defines the spans one test records")
@pytest.fixture
def spans() -> InMemorySpanExporter:
    """Returns the span recorder, cleared of earlier tests' spans.

    Returns:
        The recorder; get_finished_spans() lists this test's spans.
    """
    # log.debug("Forgets the spans earlier tests recorded")
    MEMORY.clear()
    # log.debug("Returns the recorder")
    return MEMORY
