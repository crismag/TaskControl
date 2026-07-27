"""The system clock.

Trivial, and deliberately still an adapter: the runtime depends on the port, so a test can
run a two-hour timeout in a millisecond and a replay can reconstruct a decision exactly.
"""

from __future__ import annotations

import time

from taskcontrol.domain.common.values import UtcTimestamp


class SystemClock:
    """Reads the operating system's clocks."""

    def now(self) -> UtcTimestamp:
        """Return the current instant in UTC."""
        return UtcTimestamp.now()

    def monotonic(self) -> float:
        """Return a monotonic reading in seconds.

        Uses :func:`time.monotonic`, which cannot go backwards. An NTP correction during a
        long execution must not make a duration negative or fire a timeout early.
        """
        return time.monotonic()
