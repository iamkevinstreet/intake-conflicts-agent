########################################################################
#                  backend/src/intake_agent/config.py                  #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Reads every setting the service uses, typed and validated, with the
checks that need more than one setting. Each field is a `[section] key`
in config/config.toml, joined by an underscore: `[match] likely` is
`match_likely`, which the environment variable MATCH_LIKELY overrides.

SETTINGS holds the settings loaded once at import: modules bind the
values they share from it in their global constants. Functions that take
settings as an argument keep doing so, so tests pass their own. This
service adds no secrets: Entra ID tokens are checked with the tenant's
public keys, so the model key in config/.env is the only secret it
reads.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Final, Literal, Self

# Third-party
from kds.logs import get_logger
from kds.settings import Settings
from pydantic import Field, model_validator

# Local
from intake_agent.core.names import Band

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)

########################################################################
#                           Local constants                            #
########################################################################
# log.debug("Names the sign-in mode that trusts headers, for this machine only")
DEV: Final = "dev"
# log.debug("Names the sign-in mode that checks Entra ID tokens")
ENTRA: Final = "entra"
# log.debug("Lists how callers prove who they are")
AuthMode = Literal["dev", "entra"]
# log.debug("Names this machine's own address")
LOCALHOST: Final = "127.0.0.1"
# log.debug("Lists the addresses that only this machine can reach")
LOOPBACK = frozenset({LOCALHOST, "::1", "localhost"})
# log.debug("Matches a directory (tenant) id: a GUID")
TENANT_RE = re.compile(r"^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")
# log.debug("Sets the highest score a name match can have")
TOP_SCORE = 100
# log.debug("Sets the most parties one intake may name")
MAX_PARTIES = 25
# log.debug("Sets the most model calls any run may be allowed")
MAX_STEPS = 50
# log.debug("Sets the most tool calls any run may be allowed")
MAX_TOOL_CALLS = 200
# log.debug("Sets the fewest tokens a model call may be allowed to write")
MIN_TOKENS = 100
# log.debug("Sets the smallest limit on an email's length")
MIN_EMAIL_LIMIT = 100
# log.debug("Sets the most retries a search may be allowed")
MAX_RETRIES = 5
# log.debug("Sets the smallest limit on a decision note")
MIN_NOTE_LIMIT = 10
# log.debug("Sets the hard ceiling on a decision note, above any setting")
NOTE_CEILING: Final = 2000
# log.debug("Sets the most clock skew a token may be allowed, in seconds")
MAX_LEEWAY_S = 300
# log.debug("Sets the shortest time signing keys may be cached, in seconds")
MIN_KEYS_CACHE_S = 60
# log.debug("Sets the highest port number")
MAX_PORT = 65535
# log.debug("Sets the default limit on model calls per run")
DEFAULT_STEPS = 10
# log.debug("Sets the default limit on adverse parties per draft")
DEFAULT_PARTIES = 10
# log.debug("Sets the default shortest reason to approve past a flag")
DEFAULT_REASON_CHARS = 10
# log.debug("Sets the default first wait between search retries, in seconds")
DEFAULT_BACKOFF_S = 0.2
# log.debug("Sets the default number of drafts or runs a list returns")
DEFAULT_LIST = 50
# log.debug("Sets the default most drafts or runs a list may be asked for")
DEFAULT_MAX_LIST = 200
# log.debug("Sets the shape of a draft id: D- and ten hex digits")
DRAFT_ID: Final = r"^D-[0-9a-f]{10}$"
# log.debug("Sets the shape of a run id: R- and ten hex digits")
RUN_ID: Final = r"^R-[0-9a-f]{10}$"
# log.debug("Names the role that runs intakes")
REQUESTER: Final = "requester"
# log.debug("Names the role that decides drafts and opens matters")
APPROVER: Final = "approver"
# log.debug("Names the verdict for an intake no record touches")
CLEAR: Final = "clear"
# log.debug("Names the verdict a person must decide")
REVIEW: Final = "review"
# log.debug("Names the verdict for a conflict")
CONFLICT: Final = "conflict"
# log.debug("Sets the milliseconds in a second")
MS_PER_SECOND: Final = 1000


########################################################################
#                           Service settings                           #
########################################################################
# log.debug("Defines the service's settings on top of the shared ones")
class AppSettings(Settings):
    """Intake settings; config/config.toml lists and explains each."""

    # log.debug("Holds the planted firm records the database is built around")
    data_firm: Path = Path("data/samples/firm.json")
    # log.debug("Holds the generated firm database, rebuilt when missing")
    data_database: Path = Path("data/generated/firm.sqlite")
    # log.debug("Holds the evaluation scenarios")
    data_scenarios: Path = Path("data/evals/scenarios.jsonl")
    # log.debug("Holds where evaluation results are written")
    data_results: Path = Path("data/evals/results")

    # log.debug("Holds the seed that makes the generated names repeatable")
    seed_random: int = 11
    # log.debug("Holds how many clients the database holds, planted ones included")
    seed_clients: int = Field(default=300, ge=1)
    # log.debug("Holds how many existing matters the database holds")
    seed_matters: int = Field(default=180, ge=1)
    # log.debug("Holds how many adverse parties the database holds")
    seed_adverse_parties: int = Field(default=200, ge=1)
    # log.debug("Holds the share of generated adverse parties that near-duplicate a client")
    seed_near_duplicate_share: float = Field(default=0.2, ge=0, le=1)
    # log.debug("Holds the share of generated clients that are former clients")
    seed_former_share: float = Field(default=0.25, ge=0, le=1)
    # log.debug("Holds the share of generated matters that are closed")
    seed_closed_share: float = Field(default=0.35, ge=0, le=1)

    # log.debug("Holds the score from which two names are likely the same party")
    match_likely: int = Field(default=92, ge=1, le=TOP_SCORE)
    # log.debug("Holds the score from which a person must decide")
    match_possible: int = Field(default=80, ge=1, le=TOP_SCORE)
    # log.debug("Holds the most matches one search returns")
    match_limit: int = Field(default=5, ge=1, le=MAX_PARTIES)
    # log.debug("Holds the bands that count as the same party: likely counts as exact")
    match_strong_bands: tuple[Band, ...] = ("exact", "likely")

    # log.debug("Holds the most model calls one run may make")
    agent_max_steps: int = Field(default=DEFAULT_STEPS, ge=1, le=MAX_STEPS)
    # log.debug("Holds the most tool calls one run may make")
    agent_max_tool_calls: int = Field(default=30, ge=1, le=MAX_TOOL_CALLS)
    # log.debug("Holds the most tokens one model call may write")
    agent_max_tokens: int = Field(default=1500, ge=MIN_TOKENS)
    # log.debug("Holds the most one run may spend, in US dollars")
    agent_run_budget_usd: float = Field(default=0.5, gt=0)
    # log.debug("Holds the shortest intake email accepted")
    agent_min_email_chars: int = Field(default=20, ge=1)
    # log.debug("Holds the longest intake email accepted")
    agent_max_email_chars: int = Field(default=20_000, ge=MIN_EMAIL_LIMIT)
    # log.debug("Holds the most parties one draft may name")
    agent_max_parties: int = Field(default=DEFAULT_PARTIES, ge=1, le=MAX_PARTIES)

    # log.debug("Holds how long a query waits on a busy database, in seconds")
    store_timeout_s: float = Field(default=2.0, gt=0)
    # log.debug("Holds how many times a search retries a failed read")
    store_retries: int = Field(default=2, ge=0, le=MAX_RETRIES)
    # log.debug("Holds the first wait between those retries, in seconds")
    store_backoff_s: float = Field(default=DEFAULT_BACKOFF_S, ge=0)

    # log.debug("Holds the address the server listens on; local only by default")
    api_host: str = LOCALHOST
    # log.debug("Holds the port the server listens on")
    api_port: int = Field(default=8000, ge=1, le=MAX_PORT)
    # log.debug("Holds the path every route lives under, with its version")
    api_prefix: str = "/api/v1"
    # log.debug("Holds the header that carries a request's id, both ways")
    api_request_id_header: str = "X-Request-ID"
    # log.debug("Holds how many intakes one person may run a minute")
    api_intakes_per_minute: int = Field(default=6, ge=1)
    # log.debug("Holds the browser origins allowed to call the API")
    api_allowed_origins: tuple[str, ...] = ("http://localhost:5173",)
    # log.debug("Holds the host names requests may be addressed to")
    api_allowed_hosts: tuple[str, ...] = ("localhost", LOCALHOST)
    # log.debug("Holds the shortest reason for approving over a flagged check")
    api_min_reason_chars: int = Field(default=DEFAULT_REASON_CHARS, ge=1)
    # log.debug("Holds the longest note a decision may carry")
    api_max_note_chars: int = Field(default=500, ge=MIN_NOTE_LIMIT, le=NOTE_CEILING)
    # log.debug("Holds how many drafts or runs a list returns when none is asked for")
    api_list_limit: int = Field(default=DEFAULT_LIST, ge=1)
    # log.debug("Holds the most drafts or runs a list may be asked for")
    api_max_list_limit: int = Field(default=DEFAULT_MAX_LIST, ge=1)

    # log.debug("Holds the shape of a draft id, D- and ten hex digits, which is fixed")
    ids_draft_pattern: Literal[r"^D-[0-9a-f]{10}$"] = DRAFT_ID
    # log.debug("Holds the shape of a run id, R- and ten hex digits, which is fixed")
    ids_run_pattern: Literal[r"^R-[0-9a-f]{10}$"] = RUN_ID

    # log.debug("Holds the name of the role that runs intakes, which is fixed")
    roles_requester: Literal["requester"] = REQUESTER
    # log.debug("Holds the name of the role that decides drafts, which is fixed")
    roles_approver: Literal["approver"] = APPROVER

    # log.debug("Holds the verdict for an intake no record touches, which is fixed")
    verdicts_clear: Literal["clear"] = CLEAR
    # log.debug("Holds the verdict a person must decide, which is fixed")
    verdicts_review: Literal["review"] = REVIEW
    # log.debug("Holds the verdict for a conflict, which is fixed")
    verdicts_conflict: Literal["conflict"] = CONFLICT

    # log.debug("Holds the milliseconds in a second, for timings in logs and on screen")
    units_ms_per_second: Literal[1000] = MS_PER_SECOND

    # log.debug("Holds how callers prove who they are")
    auth_mode: AuthMode = DEV
    # log.debug("Holds the Entra ID directory (tenant) id")
    entra_tenant_id: str = ""
    # log.debug("Holds the audience tokens must be issued for: this API's client id")
    entra_audience: str = ""
    # log.debug("Holds the app role that may run intakes")
    entra_requester_role: str = "Intake.Requester"
    # log.debug("Holds the app role that may approve and open matters")
    entra_approver_role: str = "Intake.Approver"
    # log.debug("Holds the clock skew allowed on token times, in seconds")
    entra_leeway_s: int = Field(default=60, ge=0, le=MAX_LEEWAY_S)
    # log.debug("Holds how long the tenant's signing keys are cached, in seconds")
    entra_keys_cache_s: int = Field(default=3600, ge=MIN_KEYS_CACHE_S)

    # log.debug("Holds the scenario ids the web app offers as examples")
    ui_examples: tuple[str, ...] = ("s04", "s09", "s13", "s18")

    # log.debug("Defines the checks that need more than one setting")
    @model_validator(mode="after")
    def _consistent(self) -> Self:
        """Refuses settings that contradict each other or are unsafe.

        Returns:
            The settings, unchanged, once every check passes.

        Raises:
            ValueError: The thresholds or list limits are out of order,
                dev sign-in would listen beyond this machine, or Entra
                ID is on without its tenant and audience.
        """
        # log.debug("Refuses a possible threshold above the likely one")
        if self.match_possible >= self.match_likely:
            # log.debug("Raises with both values")
            msg = f"[match] possible ({self.match_possible}) must be below likely"
            # log.debug("Stops the service")
            raise ValueError(msg)
        # log.debug("Refuses a default list longer than the most a list may hold")
        if self.api_list_limit > self.api_max_list_limit:
            # log.debug("Names the two limits")
            msg = f"[api] list_limit ({self.api_list_limit}) must not exceed max_list_limit"
            # log.debug("Stops the service")
            raise ValueError(msg)
        # log.debug("Refuses dev sign-in on an address other machines can reach")
        if self.auth_mode == DEV and self.api_host not in LOOPBACK:
            # log.debug("Explains that dev roles are trusted headers")
            msg = (
                f"[auth] mode = 'dev' trusts role headers, so it only listens on this machine; "
                f"set [api] host to 127.0.0.1 or [auth] mode to 'entra' (not {self.api_host})"
            )
            # log.debug("Stops the service")
            raise ValueError(msg)
        # log.debug("Refuses Entra ID without a tenant and an audience")
        if self.auth_mode == ENTRA and not (
            TENANT_RE.fullmatch(self.entra_tenant_id) and self.entra_audience
        ):
            # log.debug("Names what is missing")
            msg = "[auth] mode = 'entra' needs [entra] tenant_id (a GUID) and audience"
            # log.debug("Stops the service")
            raise ValueError(msg)
        # log.debug("Returns the settings")
        return self


# log.debug("Defines the loader every module calls")
@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    """Returns the service's settings, built and validated once.

    Tests that change the environment call
    `get_app_settings.cache_clear()`.

    Returns:
        The settings, frozen.
    """
    # log.debug("Builds and validates the settings")
    return AppSettings()


# log.debug("Loads the settings once, for the values modules share")
SETTINGS: Final = get_app_settings()
