"""Repository interfaces required by the application layer.

These are **consumer-owned contracts** (ADR 0011): defined by the code that needs them,
implemented by adapters. Nothing here knows that SQLAlchemy exists, and nothing here
returns an ORM object — a repository takes and returns domain objects, so a use case
cannot accidentally depend on how storage is shaped.

Repositories are collections, not data-access layers. They do not expose queries; they
expose the retrievals the application actually performs.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from taskcontrol.domain.common.identifiers import ExecutionId, TaskId, TaskRevisionId
from taskcontrol.domain.common.tracing import IdempotencyKey
from taskcontrol.domain.common.values import RevisionNumber, Slug
from taskcontrol.domain.execution.execution import Execution
from taskcontrol.domain.tasks.lifecycle import TaskLifecycleState
from taskcontrol.domain.tasks.revision import TaskRevision
from taskcontrol.domain.tasks.task import Task


class ConcurrencyConflictError(Exception):
    """Raised when a write would silently overwrite a concurrent change.

    Deliberately a plain exception rather than a TaskControl error: adapters translate it
    into :class:`taskcontrol.common.errors.ConflictError` at their boundary, so the port
    stays free of transport concerns.
    """


@runtime_checkable
class TaskRepository(Protocol):
    """Stores and retrieves tasks.

    Implementations must preserve optimistic concurrency: a task loaded, edited, and saved
    must fail rather than overwrite a change made by someone else in between.
    """

    def add(self, task: Task) -> None:
        """Store a new task.

        Args:
            task: The task to store.

        Raises:
            ConflictError: If a task with the same identifier or slug already exists.
        """
        ...

    def get(self, task_id: TaskId) -> Task | None:
        """Return a task by identifier.

        Args:
            task_id: The identifier.

        Returns:
            The task, or ``None`` when it does not exist.
        """
        ...

    def get_by_slug(self, slug: Slug) -> Task | None:
        """Return a task by its stable slug.

        Args:
            slug: The slug.

        Returns:
            The task, or ``None`` when it does not exist.
        """
        ...

    def update(self, task: Task, *, expected_version: int) -> int:
        """Persist changes to an existing task.

        Args:
            task: The task, carrying its new state.
            expected_version: The storage version the caller read. A mismatch means
                someone else wrote first.

        Returns:
            The new storage version.

        Raises:
            ConcurrencyConflictError: If the stored version is not ``expected_version``.
            NotFoundError: If the task does not exist.
        """
        ...

    def version_of(self, task_id: TaskId) -> int | None:
        """Return the current storage version of a task.

        Storage versions are a persistence concern, not a domain one — the domain has
        revision numbers, which mean something different. This exists so a use case can
        read a version, act, and write conditionally.

        Args:
            task_id: The identifier.

        Returns:
            The version, or ``None`` when the task does not exist.
        """
        ...

    def list_tasks(
        self,
        *,
        lifecycle_states: frozenset[TaskLifecycleState] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Task, ...]:
        """Return tasks in a stable order.

        Ordering is by identifier, which for UUIDv7 is creation order — so pagination is
        stable even while tasks are being created.

        Args:
            lifecycle_states: Restrict to these states. ``None`` means all.
            limit: Maximum number to return.
            offset: How many to skip.

        Returns:
            The matching tasks.
        """
        ...

    def count(self, *, lifecycle_states: frozenset[TaskLifecycleState] | None = None) -> int:
        """Return how many tasks match a filter.

        Args:
            lifecycle_states: Restrict to these states. ``None`` means all.

        Returns:
            The count.
        """
        ...


@runtime_checkable
class TaskRevisionRepository(Protocol):
    """Stores and retrieves task revisions.

    Revisions are append-mostly. A published revision's content never changes, so this
    port offers no general update — only the state transitions the domain permits.
    """

    def add(self, revision: TaskRevision) -> None:
        """Store a new revision.

        Args:
            revision: The revision to store.

        Raises:
            ConflictError: If the identifier, or the (task, revision number) pair, already
                exists.
        """
        ...

    def get(self, revision_id: TaskRevisionId) -> TaskRevision | None:
        """Return a revision by identifier.

        Args:
            revision_id: The identifier.

        Returns:
            The revision, or ``None`` when it does not exist.
        """
        ...

    def save_state(self, revision: TaskRevision) -> None:
        """Persist a revision's publication state and publication metadata.

        The only mutation a stored revision permits. Content is not written, because
        published content is immutable — an implementation that rewrote it would break
        the guarantee every execution record depends on.

        Args:
            revision: The revision, carrying its new publication state.

        Raises:
            NotFoundError: If the revision does not exist.
        """
        ...

    def list_for_task(
        self, task_id: TaskId, *, limit: int = 50, offset: int = 0
    ) -> tuple[TaskRevision, ...]:
        """Return a task's revisions, newest first.

        Args:
            task_id: The parent task.
            limit: Maximum number to return.
            offset: How many to skip.

        Returns:
            The revisions, ordered by revision number descending.
        """
        ...

    def latest_revision_number(self, task_id: TaskId) -> RevisionNumber | None:
        """Return the highest revision number a task has used.

        Used to allocate the next one. Revision numbers never decrease or repeat, so this
        must reflect every revision ever created, including withdrawn ones.

        Args:
            task_id: The parent task.

        Returns:
            The highest number, or ``None`` when the task has no revisions.
        """
        ...


@runtime_checkable
class ExecutionRepository(Protocol):
    """Stores and retrieves executions and their attempts.

    Executions are append-and-advance: created pending, updated as they progress, and
    frozen once terminal. There is no delete — history is the product.
    """

    def add(self, execution: Execution) -> None:
        """Store a new execution.

        Args:
            execution: The execution to store.

        Raises:
            ConflictError: If the identifier, or the task and idempotency key pair, already
                exists. A duplicate trigger delivery must not produce a second execution.
        """
        ...

    def get(self, execution_id: ExecutionId) -> Execution | None:
        """Return an execution and its attempts.

        Args:
            execution_id: The identifier.

        Returns:
            The execution, or ``None`` when it does not exist.
        """
        ...

    def find_by_idempotency_key(self, task_id: TaskId, key: IdempotencyKey) -> Execution | None:
        """Return the execution a previous identical request created, if any.

        Args:
            task_id: The task.
            key: The idempotency key supplied by the caller.

        Returns:
            The existing execution, or ``None`` when this request is new.
        """
        ...

    def save(self, execution: Execution) -> None:
        """Persist an execution's current state and its attempts.

        Must be safe to call repeatedly as an execution progresses, and must persist a
        terminal state even when called from a cleanup path after a failure.

        Args:
            execution: The execution to persist.

        Raises:
            NotFoundError: If the execution does not exist.
        """
        ...

    def list_for_task(
        self, task_id: TaskId, *, limit: int = 50, offset: int = 0
    ) -> tuple[Execution, ...]:
        """Return a task's executions, newest first.

        Args:
            task_id: The task.
            limit: Maximum number to return.
            offset: How many to skip.

        Returns:
            The executions.
        """
        ...

    def list_unfinished(self) -> tuple[Execution, ...]:
        """Return every execution that has not reached a terminal state.

        Restart recovery reads this: an execution left in flight by a process that died
        must be reconciled to an honest terminal state rather than left running forever.

        Returns:
            The unfinished executions.
        """
        ...
