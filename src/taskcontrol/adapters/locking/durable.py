"""Overlap protection backed by durable claims.

The `OverlapLock` port existed before anything could honestly implement it. Wave 3 shipped
a process-local lock, R1 measured that it protects nothing between processes, and R2
replaces it here — over the one claim primitive of ADR 0023, so scheduled overlap and queue
claiming share their ownership, expiry, and recovery semantics rather than growing two.

The lease is the only thing this adds over the claim store. A claim must expire, so a task
that outlives its lease would have its subject reclaimed while it is still running. The
lease is therefore derived from what the task is actually allowed to take, and a task with
no timeout gets a long one — long enough that expiry means "this host is gone", not "this
job is slow".
"""

from __future__ import annotations

import logging
import os
import socket
from collections.abc import Iterator
from contextlib import contextmanager

from taskcontrol.domain.claims.claim import Claim, ClaimSubject
from taskcontrol.domain.common.identifiers import TaskId
from taskcontrol.domain.common.values import Duration
from taskcontrol.ports.claims import ClaimStore
from taskcontrol.ports.lock import LockHandle, LockNotAcquiredError

logger = logging.getLogger(__name__)

DEFAULT_LEASE = Duration(3600)
"""Lease for a task with no run timeout.

An hour, not a minute: expiry is meant to recover from a dead host, not to interrupt a job
that is merely slow. A too-short lease is worse than none, because it lets a second run
start while the first is still working — which is exactly the failure this exists to stop.
"""


class DurableOverlapLock:
    """Prevents concurrent executions of one capability, across processes and restarts.

    Args:
        claims: The durable claim store.
        lease: How long a claim lasts before it lapses. Should exceed the longest run the
            protected work can legitimately take.
    """

    def __init__(self, claims: ClaimStore, *, lease: Duration = DEFAULT_LEASE) -> None:
        """Store the collaborators."""
        self._claims = claims
        self._lease = lease
        self._held: dict[str, Claim] = {}

    @property
    def scope_description(self) -> str:
        """An honest statement of what this protects.

        Read literally. It holds across processes and across restarts because the claim is
        in the database — and it holds for as long as the lease, after which a subject
        becomes claimable again whether or not its holder has finished.
        """
        return (
            f"every process sharing this database, for a lease of "
            f"{self._lease.to_primitive()} seconds"
        )

    def try_acquire(self, task_id: TaskId, *, owner: str) -> LockHandle | None:
        """Claim a capability, without waiting.

        Args:
            task_id: The capability to protect.
            owner: Identity of the would-be holder.

        Returns:
            A handle when the claim was taken, or ``None`` when another activation holds
            it.

        Raises:
            Exception: If the claim store cannot be reached. Acquisition fails rather than
                being assumed — the runtime records that as a condition error, not as
                permission to run.
        """
        subject = ClaimSubject.for_task(task_id)
        claim = self._claims.try_acquire(subject, owner=owner, lease=self._lease)

        if claim is None:
            existing = self._claims.current(subject)
            logger.info(
                "Refusing to start: this capability is already running.",
                extra={
                    "task_id": str(task_id),
                    "held_by": existing.owner if existing else "another process",
                },
            )
            return None

        handle = LockHandle(key=subject.to_primitive(), owner=owner)
        self._held[_handle_key(handle)] = claim
        return handle

    def release(self, handle: LockHandle) -> None:
        """Release a held claim.

        Releasing something not held does not raise: a process cleaning up after a crash
        must be able to call this safely.

        Args:
            handle: The handle returned by :meth:`try_acquire`.
        """
        claim = self._held.pop(_handle_key(handle), None)
        if claim is None:
            return
        self._claims.release(claim)

    def is_held(self, task_id: TaskId) -> bool:
        """Whether a live claim exists on this capability.

        For diagnostics only. Never use this to decide whether to acquire — the gap
        between checking and acquiring is a race.

        Args:
            task_id: The capability to check.

        Returns:
            ``True`` when a live claim exists.
        """
        return self._claims.current(ClaimSubject.for_task(task_id)) is not None

    @contextmanager
    def hold(self, task_id: TaskId, *, owner: str) -> Iterator[LockHandle]:
        """Hold the claim for the duration of a block, releasing it however the block ends.

        Args:
            task_id: The capability to protect.
            owner: Identity of the holder.

        Yields:
            The handle.

        Raises:
            LockNotAcquiredError: If another activation holds the claim.
        """
        handle = self.try_acquire(task_id, owner=owner)
        if handle is None:
            raise LockNotAcquiredError(
                f"Another activation of this capability is already running: {task_id}"
            )
        try:
            yield handle
        finally:
            self.release(handle)


def _handle_key(handle: LockHandle) -> str:
    """Return the key under which a handle's claim is remembered."""
    return f"{handle.key}#{handle.owner}"


def process_owner_identity() -> str:
    """Return an owner identity for this process.

    Host and process id together, because a claim's owner must be specific enough that a
    different process cannot present the same identity and release or renew a claim it
    does not hold.
    """
    return f"{socket.gethostname()}:{os.getpid()}"
