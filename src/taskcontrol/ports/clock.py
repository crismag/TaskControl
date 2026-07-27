"""The clock port.

Time is injected rather than read, because a decision that depends on the wall clock is a
decision that cannot be reproduced. Every timestamp the runtime records comes through here,
so a test can run a DST boundary or a two-hour timeout without waiting.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from taskcontrol.domain.common.values import UtcTimestamp


@runtime_checkable
class Clock(Protocol):
    """Supplies the current instant and a monotonic reading."""

    def now(self) -> UtcTimestamp:
        """Return the current instant in UTC.

        Returns:
            The instant, for recording against an execution.
        """
        ...

    def monotonic(self) -> float:
        """Return a monotonically increasing reading in seconds.

        Used for measuring elapsed time. Separate from :meth:`now` because the wall clock
        can jump — an NTP correction mid-execution must not make a duration negative or
        cause a timeout to fire early.

        Returns:
            Seconds from an arbitrary origin.
        """
        ...
