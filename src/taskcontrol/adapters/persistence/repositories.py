"""SQLAlchemy implementations of the repository ports.

Every method takes and returns domain objects. An ORM instance never leaves this module,
and neither does a session — that is what keeps `application/` free of persistence detail.

Vendor errors are translated at this boundary. A caller sees `ConflictError`, never an
``IntegrityError`` naming a constraint.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from taskcontrol.adapters.persistence import mappers
from taskcontrol.adapters.persistence.models import TaskRecord, TaskRevisionRecord
from taskcontrol.common.errors import ConflictError, NotFoundError
from taskcontrol.domain.common.identifiers import TaskId, TaskRevisionId
from taskcontrol.domain.common.values import RevisionNumber, Slug
from taskcontrol.domain.tasks.lifecycle import TaskLifecycleState
from taskcontrol.domain.tasks.revision import TaskRevision
from taskcontrol.domain.tasks.task import Task
from taskcontrol.ports.repositories import ConcurrencyConflictError


class SqlAlchemyTaskRepository:
    """Stores tasks in a relational database.

    Args:
        session: The session this repository reads and writes through. Owned by the unit
            of work, never by the repository.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, task: Task) -> None:
        """Store a new task.

        Args:
            task: The task to store.

        Raises:
            ConflictError: If the identifier or slug is already taken.
        """
        record = mappers.task_to_record(task)
        self._session.add(record)
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                "A task with this identifier or slug already exists.",
                details={"task_id": str(task.task_id), "slug": str(task.slug)},
            ) from exc

    def get(self, task_id: TaskId) -> Task | None:
        """Return a task by identifier."""
        record = self._session.get(TaskRecord, task_id.to_primitive())
        return mappers.record_to_task(record) if record else None

    def get_by_slug(self, slug: Slug) -> Task | None:
        """Return a task by slug."""
        record = self._session.scalars(
            select(TaskRecord).where(TaskRecord.slug == slug.to_primitive())
        ).one_or_none()
        return mappers.record_to_task(record) if record else None

    def update(self, task: Task, *, expected_version: int) -> int:
        """Persist changes to a task, refusing to overwrite a concurrent write.

        Args:
            task: The task carrying its new state.
            expected_version: The storage version the caller read.

        Returns:
            The new storage version.

        Raises:
            NotFoundError: If the task does not exist.
            ConcurrencyConflictError: If someone else wrote first.
        """
        record = self._session.get(TaskRecord, task.task_id.to_primitive())
        if record is None:
            raise NotFoundError("Task not found.", details={"task_id": str(task.task_id)})

        if record.storage_version != expected_version:
            raise ConcurrencyConflictError(
                f"Task {task.task_id} was modified by someone else: expected storage "
                f"version {expected_version}, found {record.storage_version}."
            )

        mappers.apply_task_to_record(record, task)
        record.storage_version = expected_version + 1

        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                "The updated task conflicts with an existing one.",
                details={"task_id": str(task.task_id), "slug": str(task.slug)},
            ) from exc

        return record.storage_version

    def version_of(self, task_id: TaskId) -> int | None:
        """Return a task's current storage version."""
        return self._session.scalars(
            select(TaskRecord.storage_version).where(TaskRecord.task_id == task_id.to_primitive())
        ).one_or_none()

    def list_tasks(
        self,
        *,
        lifecycle_states: frozenset[TaskLifecycleState] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Task, ...]:
        """Return tasks in creation order."""
        statement = select(TaskRecord)
        if lifecycle_states:
            statement = statement.where(
                TaskRecord.lifecycle_state.in_([str(state) for state in lifecycle_states])
            )
        # Identifiers are UUIDv7, so ordering by id is ordering by creation time and
        # pagination stays stable while new tasks arrive.
        statement = statement.order_by(TaskRecord.task_id).limit(limit).offset(offset)
        return tuple(mappers.record_to_task(record) for record in self._session.scalars(statement))

    def count(self, *, lifecycle_states: frozenset[TaskLifecycleState] | None = None) -> int:
        """Return how many tasks match a filter."""
        statement = select(func.count()).select_from(TaskRecord)
        if lifecycle_states:
            statement = statement.where(
                TaskRecord.lifecycle_state.in_([str(state) for state in lifecycle_states])
            )
        return self._session.scalars(statement).one()


class SqlAlchemyTaskRevisionRepository:
    """Stores task revisions in a relational database.

    Args:
        session: The session this repository reads and writes through.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, revision: TaskRevision) -> None:
        """Store a new revision.

        Args:
            revision: The revision to store.

        Raises:
            ConflictError: If the identifier, or the task and revision number pair, is
                already taken.
        """
        record = mappers.revision_to_record(revision)
        self._session.add(record)
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                "A revision with this identifier or revision number already exists for this task.",
                details={
                    "revision_id": str(revision.revision_id),
                    "task_id": str(revision.task_id),
                    "revision_number": revision.revision_number.to_primitive(),
                },
            ) from exc

    def get(self, revision_id: TaskRevisionId) -> TaskRevision | None:
        """Return a revision by identifier."""
        record = self._session.get(TaskRevisionRecord, revision_id.to_primitive())
        return mappers.record_to_revision(record) if record else None

    def save_state(self, revision: TaskRevision) -> None:
        """Persist a revision's publication state.

        Content is never written. A published revision's bytes are immutable, so this is
        deliberately the only mutation the repository offers.

        Args:
            revision: The revision carrying its new state.

        Raises:
            NotFoundError: If the revision does not exist.
        """
        record = self._session.get(TaskRevisionRecord, revision.revision_id.to_primitive())
        if record is None:
            raise NotFoundError(
                "Task revision not found.",
                details={"revision_id": str(revision.revision_id)},
            )

        mappers.apply_revision_state_to_record(record, revision)
        self._session.flush()

    def list_for_task(
        self, task_id: TaskId, *, limit: int = 50, offset: int = 0
    ) -> tuple[TaskRevision, ...]:
        """Return a task's revisions, newest first."""
        statement = (
            select(TaskRevisionRecord)
            .where(TaskRevisionRecord.task_id == task_id.to_primitive())
            .order_by(TaskRevisionRecord.revision_number.desc())
            .limit(limit)
            .offset(offset)
        )
        return tuple(
            mappers.record_to_revision(record) for record in self._session.scalars(statement)
        )

    def latest_revision_number(self, task_id: TaskId) -> RevisionNumber | None:
        """Return the highest revision number a task has used."""
        highest = self._session.scalars(
            select(func.max(TaskRevisionRecord.revision_number)).where(
                TaskRevisionRecord.task_id == task_id.to_primitive()
            )
        ).one()
        return RevisionNumber(highest) if highest is not None else None
