"""Overlap lock implementations.

There is currently **no production implementation**. `ProcessLocalOverlapLock` is a test
double: it guards a single process, which under cron-backed activation means it guards
nothing, because every activation is a separate process.

Durable claims — one capability serving both scheduled overlap and work-item claiming — are
delivered in R2 (ADR 0023). Until then TaskControl makes no overlap guarantee.
"""

from __future__ import annotations

from taskcontrol.adapters.locking.no_overlap_protection import NoOverlapProtection
from taskcontrol.adapters.locking.process_local import (
    SCOPE_DESCRIPTION,
    ProcessLocalOverlapLock,
)

__all__ = ["SCOPE_DESCRIPTION", "NoOverlapProtection", "ProcessLocalOverlapLock"]
