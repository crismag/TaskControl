"""Overlap lock implementations.

Phase 1 ships one: `ProcessLocalOverlapLock`, which guarantees non-overlap **within a
single TaskControl process and nowhere wider**. Durable, multi-process locking is a Wave 5
requirement (ADR 0021).
"""

from __future__ import annotations

from taskcontrol.adapters.locking.process_local import (
    SCOPE_DESCRIPTION,
    ProcessLocalOverlapLock,
)

__all__ = ["SCOPE_DESCRIPTION", "ProcessLocalOverlapLock"]
