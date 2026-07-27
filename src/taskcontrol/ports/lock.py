"""The overlap lock port.

A task with an overlap policy of ``FORBID`` promises that two of its executions will not
run at the same time. This port is how the runtime makes that promise without knowing what
enforces it.

The production implementation is
:class:`taskcontrol.adapters.locking.durable.DurableOverlapLock`, which holds its claim in
the database over the one claim primitive of ADR 0023. It protects across processes and
across restarts — the only kind of protection worth anything under cron-backed activation,
where every activation is a separate process.

`ProcessLocalOverlapLock` remains as a test double for in-process unit tests. It guards a
single process, which between cron activations is not weaker protection but none at all
(measured in R1). It must never be wired into a production path, and a test asserts that.

The runtime depends on this port and never on an implementation, which is what allowed the
inert lock to be replaced without reworking any orchestration.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from taskcontrol.domain.common.identifiers import TaskId


@dataclass(frozen=True, slots=True)
class LockHandle:
    """Proof that a lock is held.

    Attributes:
        key: What is locked.
        owner: Who holds it. Opaque to the runtime; an implementation uses whatever
            identity it can actually verify.
    """

    key: str
    owner: str


class LockNotAcquiredError(Exception):
    """Raised when a lock is already held.

    A plain exception rather than a TaskControl error: the runtime converts contention into
    a recorded ``BLOCKED`` execution with reason code ``blocked.overlap_lock_held``, so the
    port stays free of outcome vocabulary.
    """


@runtime_checkable
class OverlapLock(Protocol):
    """Prevents concurrent executions of one task.

    An implementation must state the boundary within which its guarantee holds. A lock that
    claims more than it delivers is worse than no lock, because operators trust it.
    """

    @property
    def scope_description(self) -> str:
        """A short, honest statement of what this lock actually protects.

        Surfaced in diagnostics so an operator can tell what guarantee is in force without
        reading source. For example: ``"this TaskControl process only"``.
        """
        ...

    def try_acquire(self, task_id: TaskId, *, owner: str) -> LockHandle | None:
        """Attempt to take the lock without waiting.

        Never blocks. A task that cannot start now should be recorded as ``BLOCKED`` and
        explained, not left waiting on a lock while its schedule moves on.

        Args:
            task_id: The task to lock.
            owner: Identity of the would-be holder.

        Returns:
            A handle when the lock was taken, or ``None`` when it is already held.

        Raises:
            Exception: If the lock store cannot be reached. An implementation must never
                assume acquisition when it cannot tell — the runtime treats that as
                ``CONDITION_ERROR``, not as permission to run.
        """
        ...

    def release(self, handle: LockHandle) -> None:
        """Release a held lock.

        Releasing a lock that is not held, or one held by a different owner, must not raise.
        A runtime cleaning up after a crash should be able to call this safely.

        Args:
            handle: The handle returned by :meth:`try_acquire`.
        """
        ...

    def is_held(self, task_id: TaskId) -> bool:
        """Whether the lock is currently held.

        For diagnostics only. Never use this to decide whether to acquire — the gap between
        checking and acquiring is a race.

        Args:
            task_id: The task to check.

        Returns:
            ``True`` when held.
        """
        ...

    @contextmanager
    def hold(self, task_id: TaskId, *, owner: str) -> Iterator[LockHandle]:
        """Hold the lock for the duration of a block, releasing it however the block ends.

        Args:
            task_id: The task to lock.
            owner: Identity of the holder.

        Yields:
            The handle.

        Raises:
            LockNotAcquiredError: If the lock is already held.
        """
        ...
