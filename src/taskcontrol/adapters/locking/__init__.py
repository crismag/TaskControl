"""Overlap lock implementations.

`DurableOverlapLock` is the production implementation. It holds its claim in the database,
so it protects across processes and restarts — which is the only kind of protection worth
anything under cron-backed activation, where every activation is a separate process.

`ProcessLocalOverlapLock` remains a test double for in-process unit tests, and
`NoOverlapProtection` for composition that deliberately runs without protection. Neither
may be wired into a production path (ADR 0023), and a test asserts that.
"""

from __future__ import annotations

from taskcontrol.adapters.locking.durable import (
    DEFAULT_LEASE,
    DurableOverlapLock,
    process_owner_identity,
)
from taskcontrol.adapters.locking.no_overlap_protection import NoOverlapProtection
from taskcontrol.adapters.locking.process_local import (
    SCOPE_DESCRIPTION,
    ProcessLocalOverlapLock,
)

__all__ = [
    "DEFAULT_LEASE",
    "SCOPE_DESCRIPTION",
    "DurableOverlapLock",
    "NoOverlapProtection",
    "ProcessLocalOverlapLock",
    "process_owner_identity",
]
