"""Overlap locking within one process: a test double, not for production use.

.. warning::

   Under cron-backed activation this lock provides **no overlap protection at all**. Every
   cron activation is a separate process, and this lock holds its state in memory, so two
   activations of the same task will both run.

   That is not a prediction. R1 measured it: two concurrent activations of a task with
   ``OverlapPolicy.FORBID`` both executed to completion. See
   ``development/reviews/R1_WAVE3_COMPATIBILITY.md``, Finding 1.

   Durable claims (ADR 0023) replace this for every real activation path. Until they exist,
   TaskControl makes **no** overlap guarantee, and this class exists only so in-process
   tests can exercise the ``OverlapLock`` port.

**Scope of the guarantee.** This lock prevents two executions of a task overlapping *inside
a single TaskControl process*. That is all.

It does **not** protect against:

* a second TaskControl process on the same host;
* an API process and a separate worker process;
* multiple hosts sharing one database;
* a process that was killed while holding a lock, which simply loses it along with its
  memory.

It is not durable, not distributed, and not multi-worker safe. The class is named
``ProcessLocalOverlapLock`` so that a reader encountering it in a stack trace, a log line,
or an autocomplete list learns the limitation without having to look it up.

Durable claims — row-level ownership, leases, and stale-claim recovery, serving both
scheduled overlap and work-item claiming — are delivered in **R2**. See **ADR 0023**, which
supersedes ADR 0021.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from taskcontrol.domain.common.identifiers import TaskId
from taskcontrol.infrastructure.logging import get_logger
from taskcontrol.ports.lock import LockHandle, LockNotAcquiredError

logger = get_logger(__name__)

SCOPE_DESCRIPTION = "this TaskControl process only"
"""Stated wherever the guarantee is surfaced. Deliberately narrow and deliberately blunt."""


class ProcessLocalOverlapLock:
    """Prevent overlapping executions of one task within this process (test double).

    Thread-safe. Not process-safe, not host-safe, not cluster-safe — and therefore useless
    for cron-backed activation, where every activation is a separate process. Use only in
    tests that exercise the port in one process; see the module docstring, ADR 0023, and
    R1 Finding 1.

    Acquisition never waits. A task that cannot start now is recorded as ``BLOCKED`` and
    explained; blocking on a lock would leave an execution invisible while its schedule
    moves on without it.
    """

    def __init__(self) -> None:
        # One mutex guarding a dict of held keys. Per-key locks would be lighter, but this
        # is contended only at acquire and release, and the simpler structure is easier to
        # reason about than a lock over a map of locks.
        self._guard = threading.Lock()
        self._held: dict[str, str] = {}

    @property
    def scope_description(self) -> str:
        """What this lock actually protects: this process, and nothing wider."""
        return SCOPE_DESCRIPTION

    def try_acquire(self, task_id: TaskId, *, owner: str) -> LockHandle | None:
        """Attempt to take the lock without waiting.

        Args:
            task_id: The task to lock.
            owner: Identity of the would-be holder.

        Returns:
            A handle when taken, or ``None`` when another holder has it.
        """
        key = self._key(task_id)
        with self._guard:
            existing = self._held.get(key)
            if existing is not None:
                logger.info(
                    "Overlap lock already held",
                    extra={
                        "task_id": str(task_id),
                        "held_by": existing,
                        "requested_by": owner,
                        "lock_scope": SCOPE_DESCRIPTION,
                    },
                )
                return None
            self._held[key] = owner

        return LockHandle(key=key, owner=owner)

    def release(self, handle: LockHandle) -> None:
        """Release a held lock.

        Releasing a lock that is not held, or one held by someone else, is a no-op rather
        than an error: cleanup paths run after failures, and a crash-recovery routine must
        be able to call this without first proving it is safe.

        Args:
            handle: The handle returned by :meth:`try_acquire`.
        """
        with self._guard:
            current = self._held.get(handle.key)
            if current is None:
                return
            if current != handle.owner:
                logger.warning(
                    "Refusing to release an overlap lock held by a different owner",
                    extra={
                        "lock_key": handle.key,
                        "held_by": current,
                        "release_attempted_by": handle.owner,
                    },
                )
                return
            del self._held[handle.key]

    def is_held(self, task_id: TaskId) -> bool:
        """Whether the lock is currently held, for diagnostics only.

        Never decide whether to acquire from this: the gap between checking and acquiring
        is a race. Use :meth:`try_acquire` and act on its answer.

        Args:
            task_id: The task to check.

        Returns:
            ``True`` when held.
        """
        with self._guard:
            return self._key(task_id) in self._held

    def holder_of(self, task_id: TaskId) -> str | None:
        """Return who holds the lock, for diagnostics and error messages.

        Args:
            task_id: The task to check.

        Returns:
            The owner identity, or ``None`` when the lock is free.
        """
        with self._guard:
            return self._held.get(self._key(task_id))

    @contextmanager
    def hold(self, task_id: TaskId, *, owner: str) -> Iterator[LockHandle]:
        """Hold the lock for the duration of a block.

        The lock is released however the block ends, including on an exception — a lock
        leaked by a failure path would block the task until the process restarts.

        Args:
            task_id: The task to lock.
            owner: Identity of the holder.

        Yields:
            The handle.

        Raises:
            LockNotAcquiredError: If another holder already has it.
        """
        handle = self.try_acquire(task_id, owner=owner)
        if handle is None:
            message = (
                f"Overlap lock for task {task_id} is already held "
                f"by {self.holder_of(task_id)!r} in {SCOPE_DESCRIPTION}."
            )
            raise LockNotAcquiredError(message)
        try:
            yield handle
        finally:
            self.release(handle)

    @staticmethod
    def _key(task_id: TaskId) -> str:
        """Return the lock key for a task."""
        return f"task:{task_id.to_primitive()}"
