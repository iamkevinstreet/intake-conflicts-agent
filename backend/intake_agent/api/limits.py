########################################################################
#                  backend/intake_agent/api/limits.py                  #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           A per-person limit on intakes over a rolling     #
#                     minute, held in memory.                          #
########################################################################
"""A per-person rate limit over a rolling window.

It keeps recent request times in memory, per person, so it
holds for one server process. Behind a proxy or with several workers,
the limit belongs in the proxy or a shared store instead; the README
lists this under unresolved questions.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from kds.logs import get_logger

# Module constants
log = get_logger(__name__)
# log.debug("Sets the window the limit counts over, in seconds")
WINDOW_S = 60.0


# log.debug("Defines the limiter")
class RateLimiter:
    """At most `limit` requests per client in any rolling window."""

    # log.debug("Defines the constructor")
    def __init__(
        self, limit: int, window_s: float = WINDOW_S, clock: Callable[[], float] = time.monotonic
    ) -> None:
        """Allow `limit` requests per client per `window_s` seconds."""
        # log.debug("Keeps the limit")
        self.limit = limit
        # log.debug("Keeps the window length")
        self.window_s = window_s
        # log.debug("Keeps the clock, which tests replace")
        self.clock = clock
        # log.debug("Starts each client's list of recent request times")
        self._seen: defaultdict[str, deque[float]] = defaultdict(deque)
        # log.debug("Creates the lock that guards those lists")
        self._lock = threading.Lock()

    # log.debug("Defines the check for one request")
    def allow(self, client: str) -> bool:
        """Record a request; return False when over the limit."""
        # log.debug("Reads the time now")
        now = self.clock()
        # log.debug("Updates the client's list under the lock")
        with self._lock:
            # log.debug("Takes the client's recent request times")
            seen = self._seen[client]
            # log.debug("Forgets requests older than the window")
            while seen and now - seen[0] >= self.window_s:
                # log.debug("Drops the oldest request time")
                seen.popleft()
            # log.debug("Refuses the request when the window is full")
            if len(seen) >= self.limit:
                # log.debug("Returns refused")
                return False
            # log.debug("Records this request")
            seen.append(now)
        # log.debug("Returns allowed")
        return True
