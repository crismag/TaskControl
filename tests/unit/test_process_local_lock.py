"""Contract tests for the overlap lock port.

These are written against the **port**, not the implementation, so the durable lock Wave 5
introduces must pass them unchanged (ADR 0021).

Same-process contention is the behaviour Phase 1 actually guarantees, and it is what these
tests prove. They deliberately do **not** assert anything about multiple processes, because
`ProcessLocalOverlapLock` makes no such promise and a test implying otherwise would be
worse than no test.
"""

from __future__ import annotations

import threading
import time

import pytest

from taskcontrol.adapters.locking import SCOPE_DESCRIPTION, ProcessLocalOverlapLock
from taskcontrol.domain.common import TaskId
from taskcontrol.ports.lock import LockHandle, LockNotAcquiredError, OverlapLock


@pytest.fixture
def lock() -> ProcessLocalOverlapLock:
    """Return a fresh lock."""
    return ProcessLocalOverlapLock()


class TestPortConformance:
    def test_the_implementation_satisfies_the_port(self, lock: ProcessLocalOverlapLock) -> None:
        """The runtime depends on the port, so the adapter must actually implement it."""
        assert isinstance(lock, OverlapLock)

    def test_the_scope_is_stated_honestly(self, lock: ProcessLocalOverlapLock) -> None:
        """An operator must be able to learn the guarantee without reading source."""
        assert lock.scope_description == SCOPE_DESCRIPTION
        assert "process" in lock.scope_description

    def test_the_class_name_names_the_limitation(self) -> None:
        """A lock that looks durable and is not is worse than an honest one (ADR 0021)."""
        assert "ProcessLocal" in ProcessLocalOverlapLock.__name__

    def test_no_wider_guarantee_is_claimed(self) -> None:
        """Nothing in the documentation may suggest durability or distribution."""
        documentation = " ".join(
            text.lower()
            for text in (
                ProcessLocalOverlapLock.__doc__ or "",
                ProcessLocalOverlapLock.scope_description.__doc__ or "",
                SCOPE_DESCRIPTION,
            )
        )
        for overclaim in ("is durable", "is distributed", "cluster-wide", "multi-worker safe"):
            assert overclaim not in documentation


class TestAcquisition:
    def test_a_free_lock_is_acquired(self, lock: ProcessLocalOverlapLock) -> None:
        assert lock.try_acquire(TaskId.generate(), owner="runner-1") is not None

    def test_acquisition_marks_the_lock_held(self, lock: ProcessLocalOverlapLock) -> None:
        task_id = TaskId.generate()
        lock.try_acquire(task_id, owner="runner-1")
        assert lock.is_held(task_id)

    def test_the_handle_records_the_owner(self, lock: ProcessLocalOverlapLock) -> None:
        handle = lock.try_acquire(TaskId.generate(), owner="runner-1")
        assert handle is not None
        assert handle.owner == "runner-1"

    def test_different_tasks_do_not_contend(self, lock: ProcessLocalOverlapLock) -> None:
        """The lock is per task; one busy task must not stop the whole estate."""
        assert lock.try_acquire(TaskId.generate(), owner="a") is not None
        assert lock.try_acquire(TaskId.generate(), owner="b") is not None


class TestSameProcessContention:
    """The guarantee Phase 1 actually makes."""

    def test_a_second_acquisition_is_refused(self, lock: ProcessLocalOverlapLock) -> None:
        task_id = TaskId.generate()
        assert lock.try_acquire(task_id, owner="first") is not None
        assert lock.try_acquire(task_id, owner="second") is None

    def test_refusal_does_not_wait(self, lock: ProcessLocalOverlapLock) -> None:
        """Blocking would leave an execution invisible while its schedule moves on."""
        task_id = TaskId.generate()
        lock.try_acquire(task_id, owner="first")

        started = time.monotonic()
        lock.try_acquire(task_id, owner="second")
        assert time.monotonic() - started < 0.5

    def test_the_holder_is_reported(self, lock: ProcessLocalOverlapLock) -> None:
        """Contention must be explainable, so the error can name who holds it."""
        task_id = TaskId.generate()
        lock.try_acquire(task_id, owner="execution-abc")
        assert lock.holder_of(task_id) == "execution-abc"

    def test_the_lock_frees_after_release(self, lock: ProcessLocalOverlapLock) -> None:
        task_id = TaskId.generate()
        handle = lock.try_acquire(task_id, owner="first")
        assert handle is not None

        lock.release(handle)

        assert not lock.is_held(task_id)
        assert lock.try_acquire(task_id, owner="second") is not None

    def test_concurrent_threads_produce_exactly_one_winner(
        self, lock: ProcessLocalOverlapLock
    ) -> None:
        """The race the lock exists to settle, run for real rather than reasoned about."""
        task_id = TaskId.generate()
        acquired: list[str] = []
        barrier = threading.Barrier(8)

        def contend(index: int) -> None:
            barrier.wait()
            if lock.try_acquire(task_id, owner=f"runner-{index}") is not None:
                acquired.append(f"runner-{index}")

        threads = [threading.Thread(target=contend, args=(index,)) for index in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(acquired) == 1, f"expected exactly one winner, got {acquired}"

    def test_repeated_contention_stays_consistent(self, lock: ProcessLocalOverlapLock) -> None:
        """Acquire and release many times; the lock must not leak or double-grant."""
        task_id = TaskId.generate()
        for index in range(50):
            handle = lock.try_acquire(task_id, owner=f"runner-{index}")
            assert handle is not None, f"iteration {index} failed to acquire"
            assert lock.try_acquire(task_id, owner="intruder") is None
            lock.release(handle)
        assert not lock.is_held(task_id)


class TestRelease:
    def test_releasing_an_unheld_lock_is_safe(self, lock: ProcessLocalOverlapLock) -> None:
        """Cleanup paths run after failures and must not need to prove it is safe first."""
        lock.release(LockHandle(key="task:never-held", owner="ghost"))

    def test_releasing_twice_is_safe(self, lock: ProcessLocalOverlapLock) -> None:
        handle = lock.try_acquire(TaskId.generate(), owner="first")
        assert handle is not None
        lock.release(handle)
        lock.release(handle)

    def test_another_owner_cannot_release_the_lock(self, lock: ProcessLocalOverlapLock) -> None:
        """A stale handle from a previous run must not free someone else's lock."""
        task_id = TaskId.generate()
        handle = lock.try_acquire(task_id, owner="rightful-owner")
        assert handle is not None

        lock.release(LockHandle(key=handle.key, owner="imposter"))

        assert lock.is_held(task_id)
        assert lock.holder_of(task_id) == "rightful-owner"


class TestHoldContextManager:
    def test_the_lock_is_held_inside_the_block(self, lock: ProcessLocalOverlapLock) -> None:
        task_id = TaskId.generate()
        with lock.hold(task_id, owner="runner"):
            assert lock.is_held(task_id)
        assert not lock.is_held(task_id)

    def test_the_lock_is_released_on_an_exception(self, lock: ProcessLocalOverlapLock) -> None:
        """A leaked lock would block the task until the process restarts."""
        task_id = TaskId.generate()
        with pytest.raises(RuntimeError), lock.hold(task_id, owner="runner"):
            message = "the work failed"
            raise RuntimeError(message)
        assert not lock.is_held(task_id)

    def test_contention_raises_with_an_explanatory_message(
        self, lock: ProcessLocalOverlapLock
    ) -> None:
        task_id = TaskId.generate()
        lock.try_acquire(task_id, owner="first")

        with pytest.raises(LockNotAcquiredError) as caught, lock.hold(task_id, owner="second"):
            pass  # pragma: no cover - never entered

        message = str(caught.value)
        assert "first" in message
        assert SCOPE_DESCRIPTION in message, "the message must state the guarantee's scope"
