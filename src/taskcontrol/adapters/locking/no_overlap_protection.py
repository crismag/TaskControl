"""The honest absence of overlap protection.

TaskControl has no production overlap lock yet. Durable claims — the one capability serving
both scheduled overlap and work-item claiming — arrive in R2 (ADR 0023).

Until then something must satisfy the `OverlapLock` port, and the choice matters. Wiring
`ProcessLocalOverlapLock` would be worse than wiring nothing: it guards a single process,
which under cron-backed activation guards nothing at all (R1 Finding 1), while *looking*
like protection in a stack trace and a code review.

This implementation always grants the claim and logs that it did so. A caller reading the
logs learns the truth; a caller reading the code sees a class named for what it does.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from taskcontrol.domain.common.identifiers import TaskId
from taskcontrol.infrastructure.logging import get_logger
from taskcontrol.ports.lock import LockHandle

logger = get_logger(__name__)

SCOPE_DESCRIPTION = "none — overlap protection is not yet implemented"
"""Surfaced wherever the guarantee is reported. Deliberately blunt."""


class NoOverlapProtection:
    """Grants every claim, and records that overlap was not prevented.

    Satisfies the `OverlapLock` port without pretending to protect anything. Replaced by the
    durable claim implementation in R2.
    """

    @property
    def scope_description(self) -> str:
        """State plainly that nothing is protected."""
        return SCOPE_DESCRIPTION

    def try_acquire(self, task_id: TaskId, *, owner: str) -> LockHandle | None:
        """Always grant, and warn that overlap is unprotected.

        Args:
            task_id: The task nominally being locked.
            owner: The would-be holder.

        Returns:
            A handle, always. Never ``None``.
        """
        logger.warning(
            "Proceeding without overlap protection; a concurrent activation of this task "
            "would also run. Durable claims arrive in R2 (ADR 0023).",
            extra={"task_id": str(task_id), "owner": owner},
        )
        return LockHandle(key=f"task:{task_id.to_primitive()}", owner=owner)

    def release(self, handle: LockHandle) -> None:
        """Do nothing; nothing was held.

        Args:
            handle: Ignored.
        """

    def is_held(self, task_id: TaskId) -> bool:
        """Return ``False``: nothing is ever held.

        Args:
            task_id: Ignored.

        Returns:
            Always ``False``.
        """
        _ = task_id
        return False

    @contextmanager
    def hold(self, task_id: TaskId, *, owner: str) -> Iterator[LockHandle]:
        """Yield a granted handle. Never refuses.

        Args:
            task_id: The task nominally being locked.
            owner: The holder.

        Yields:
            The handle.
        """
        handle = self.try_acquire(task_id, owner=owner)
        assert handle is not None  # noqa: S101 - this implementation never refuses
        try:
            yield handle
        finally:
            self.release(handle)
