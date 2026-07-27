"""Repository contract tests, run against every available backend.

One suite, two backends. A behaviour that only holds on SQLite is not a behaviour
TaskControl has, and the point of running the same assertions against PostgreSQL is to
find that out before a release rather than after a migration.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, text

from taskcontrol.adapters.persistence.unit_of_work import UnitOfWork
from taskcontrol.common.errors import ConflictError, NotFoundError
from taskcontrol.domain.common import (
    Duration,
    OwnerId,
    RevisionNumber,
    Slug,
    TaskId,
    TaskRevisionId,
    UtcTimestamp,
)
from taskcontrol.domain.execution import RetryPolicy, TimeoutPolicy
from taskcontrol.domain.tasks import (
    ActionSpecification,
    EnvironmentBinding,
    ExecutionControls,
    ExecutorType,
    PublicationState,
    Task,
    TaskLifecycleState,
    TaskRevision,
)
from taskcontrol.ports.repositories import (
    ConcurrencyConflictError,
    TaskRepository,
    TaskRevisionRepository,
)

pytestmark = pytest.mark.integration

NOW = UtcTimestamp(datetime(2026, 7, 27, 6, 0, tzinfo=UTC))
LATER = UtcTimestamp(datetime(2026, 7, 27, 7, 30, tzinfo=UTC))
ACTOR = OwnerId.generate()


def a_task(name: str = "Daily Settlement Report") -> Task:
    """Build a draft task."""
    return Task.create(name=name, owner_id=ACTOR, created_by=ACTOR, created_at=NOW)


def a_revision(task: Task, number: int = 1, **overrides: object) -> TaskRevision:
    """Build a draft revision for a task."""
    defaults: dict[str, object] = {
        "revision_id": TaskRevisionId.generate(),
        "task_id": task.task_id,
        "revision_number": RevisionNumber(number),
        "action": ActionSpecification(
            executor_type=ExecutorType.SHELL,
            entrypoint="/usr/bin/bash",
            arguments=("/opt/tasks/report.sh", "--date", "2026-07-27"),
            working_directory="/opt/tasks",
            environment=(EnvironmentBinding("REGION", value="eu-west-1"),),
        ),
        "created_at": NOW,
        "created_by": ACTOR,
        "controls": ExecutionControls(
            timeout=TimeoutPolicy(run_timeout=Duration(1200), termination_grace=Duration(30)),
            retry=RetryPolicy(max_attempts=3),
        ),
        "change_summary": "Initial definition.",
    }
    return TaskRevision(**(defaults | overrides))  # type: ignore[arg-type]


class TestPortConformance:
    def test_repositories_satisfy_their_ports(self, unit_of_work: UnitOfWork) -> None:
        """The adapters must actually implement the contracts the application depends on."""
        with unit_of_work as uow:
            assert isinstance(uow.tasks, TaskRepository)
            assert isinstance(uow.revisions, TaskRevisionRepository)


class TestTaskRepository:
    def test_stores_and_retrieves_a_task(self, unit_of_work: UnitOfWork) -> None:
        task = a_task()
        with unit_of_work as uow:
            uow.tasks.add(task)
            uow.commit()

        with unit_of_work as uow:
            assert uow.tasks.get(task.task_id) == task

    def test_returns_none_for_an_unknown_task(self, unit_of_work: UnitOfWork) -> None:
        with unit_of_work as uow:
            assert uow.tasks.get(TaskId.generate()) is None

    def test_retrieves_by_slug(self, unit_of_work: UnitOfWork) -> None:
        task = a_task()
        with unit_of_work as uow:
            uow.tasks.add(task)
            uow.commit()

        with unit_of_work as uow:
            found = uow.tasks.get_by_slug(Slug("daily-settlement-report"))
            assert found is not None
            assert found.task_id == task.task_id

    def test_rejects_a_duplicate_slug(self, unit_of_work: UnitOfWork) -> None:
        """A slug appears in URLs and artefacts, so it must identify exactly one task."""
        with unit_of_work as uow:
            uow.tasks.add(a_task())
            uow.commit()

        with unit_of_work as uow, pytest.raises(ConflictError):
            uow.tasks.add(a_task())

    def test_updates_a_task(self, unit_of_work: UnitOfWork) -> None:
        task = a_task()
        with unit_of_work as uow:
            uow.tasks.add(task)
            uow.commit()

        renamed = task.update_metadata(name="Settlement Report", updated_by=ACTOR, updated_at=LATER)
        with unit_of_work as uow:
            version = uow.tasks.version_of(task.task_id)
            assert version is not None
            uow.tasks.update(renamed, expected_version=version)
            uow.commit()

        with unit_of_work as uow:
            stored = uow.tasks.get(task.task_id)
            assert stored is not None
            assert stored.name == "Settlement Report"
            assert stored.updated_at == LATER

    def test_update_of_a_missing_task_raises(self, unit_of_work: UnitOfWork) -> None:
        with unit_of_work as uow, pytest.raises(NotFoundError):
            uow.tasks.update(a_task(), expected_version=1)

    def test_lists_tasks_in_creation_order(self, unit_of_work: UnitOfWork) -> None:
        """UUIDv7 ordering means pagination stays stable while tasks are being created."""
        names = ["Alpha Job", "Bravo Job", "Charlie Job"]
        created = [a_task(name) for name in names]
        with unit_of_work as uow:
            for task in created:
                uow.tasks.add(task)
            uow.commit()

        with unit_of_work as uow:
            listed = uow.tasks.list_tasks()
            assert [task.task_id for task in listed] == sorted(task.task_id for task in created)

    def test_filters_by_lifecycle_state(self, unit_of_work: UnitOfWork) -> None:
        draft = a_task("Draft Job")
        active_task = a_task("Active Job")
        revision = a_revision(active_task).publish(published_by=ACTOR, published_at=NOW)
        active_task = active_task.activate_revision(
            revision.revision_id, updated_by=ACTOR, updated_at=NOW
        )

        with unit_of_work as uow:
            uow.tasks.add(draft)
            uow.tasks.add(active_task)
            uow.revisions.add(revision)
            uow.commit()

        with unit_of_work as uow:
            actives = uow.tasks.list_tasks(lifecycle_states=frozenset({TaskLifecycleState.ACTIVE}))
            assert [task.name for task in actives] == ["Active Job"]
            assert uow.tasks.count() == 2
            assert uow.tasks.count(lifecycle_states=frozenset({TaskLifecycleState.DRAFT})) == 1

    def test_paginates(self, unit_of_work: UnitOfWork) -> None:
        with unit_of_work as uow:
            for index in range(5):
                uow.tasks.add(a_task(f"Job Number {index}"))
            uow.commit()

        with unit_of_work as uow:
            first = uow.tasks.list_tasks(limit=2, offset=0)
            second = uow.tasks.list_tasks(limit=2, offset=2)
            assert len(first) == 2
            assert len(second) == 2
            assert {task.task_id for task in first}.isdisjoint({task.task_id for task in second})


class TestOptimisticConcurrency:
    def test_a_stale_write_is_refused(self, unit_of_work: UnitOfWork) -> None:
        """Two editors, one loses — rather than silently overwriting the other."""
        task = a_task()
        with unit_of_work as uow:
            uow.tasks.add(task)
            uow.commit()

        with unit_of_work as uow:
            stale_version = uow.tasks.version_of(task.task_id)
            assert stale_version is not None

        first = task.update_metadata(name="First Edit", updated_by=ACTOR, updated_at=LATER)
        with unit_of_work as uow:
            uow.tasks.update(first, expected_version=stale_version)
            uow.commit()

        second = task.update_metadata(name="Second Edit", updated_by=ACTOR, updated_at=LATER)
        with unit_of_work as uow, pytest.raises(ConcurrencyConflictError):
            uow.tasks.update(second, expected_version=stale_version)

    def test_the_version_increments_on_write(self, unit_of_work: UnitOfWork) -> None:
        task = a_task()
        with unit_of_work as uow:
            uow.tasks.add(task)
            uow.commit()

        with unit_of_work as uow:
            before = uow.tasks.version_of(task.task_id)
            assert before is not None
            after = uow.tasks.update(
                task.update_metadata(name="Renamed", updated_by=ACTOR, updated_at=LATER),
                expected_version=before,
            )
            uow.commit()

        assert after == before + 1

    def test_the_losing_write_left_no_trace(self, unit_of_work: UnitOfWork) -> None:
        task = a_task()
        with unit_of_work as uow:
            uow.tasks.add(task)
            uow.commit()

        with unit_of_work as uow:
            version = uow.tasks.version_of(task.task_id)
            assert version is not None

        with unit_of_work as uow:
            uow.tasks.update(
                task.update_metadata(name="Winner", updated_by=ACTOR, updated_at=LATER),
                expected_version=version,
            )
            uow.commit()

        with unit_of_work as uow, pytest.raises(ConcurrencyConflictError):
            uow.tasks.update(
                task.update_metadata(name="Loser", updated_by=ACTOR, updated_at=LATER),
                expected_version=version,
            )

        with unit_of_work as uow:
            stored = uow.tasks.get(task.task_id)
            assert stored is not None
            assert stored.name == "Winner"


class TestRevisionRepository:
    def test_stores_and_retrieves_a_revision(self, unit_of_work: UnitOfWork) -> None:
        task = a_task()
        revision = a_revision(task)
        with unit_of_work as uow:
            uow.tasks.add(task)
            uow.revisions.add(revision)
            uow.commit()

        with unit_of_work as uow:
            assert uow.revisions.get(revision.revision_id) == revision

    def test_a_published_revision_round_trips_with_its_digest(
        self, unit_of_work: UnitOfWork
    ) -> None:
        """A digest that changed in storage would break deployment integrity."""
        task = a_task()
        revision = a_revision(task).publish(published_by=ACTOR, published_at=NOW)
        with unit_of_work as uow:
            uow.tasks.add(task)
            uow.revisions.add(revision)
            uow.commit()

        with unit_of_work as uow:
            stored = uow.revisions.get(revision.revision_id)
            assert stored is not None
            assert stored.content_digest == revision.content_digest
            assert stored.compute_digest() == revision.compute_digest()

    def test_rejects_a_duplicate_revision_number(self, unit_of_work: UnitOfWork) -> None:
        """Revision numbers never repeat, and the database makes that impossible."""
        task = a_task()
        with unit_of_work as uow:
            uow.tasks.add(task)
            uow.revisions.add(a_revision(task, number=1))
            uow.commit()

        with unit_of_work as uow, pytest.raises(ConflictError):
            uow.revisions.add(a_revision(task, number=1))

    def test_lists_revisions_newest_first(self, unit_of_work: UnitOfWork) -> None:
        task = a_task()
        with unit_of_work as uow:
            uow.tasks.add(task)
            for number in (1, 2, 3):
                uow.revisions.add(a_revision(task, number=number))
            uow.commit()

        with unit_of_work as uow:
            numbers = [
                revision.revision_number.value
                for revision in uow.revisions.list_for_task(task.task_id)
            ]
            assert numbers == [3, 2, 1]

    def test_reports_the_latest_revision_number(self, unit_of_work: UnitOfWork) -> None:
        task = a_task()
        with unit_of_work as uow:
            uow.tasks.add(task)
            assert uow.revisions.latest_revision_number(task.task_id) is None
            for number in (1, 2):
                uow.revisions.add(a_revision(task, number=number))
            uow.commit()

        with unit_of_work as uow:
            assert uow.revisions.latest_revision_number(task.task_id) == RevisionNumber(2)

    def test_saves_a_publication_state_transition(self, unit_of_work: UnitOfWork) -> None:
        task = a_task()
        draft = a_revision(task)
        with unit_of_work as uow:
            uow.tasks.add(task)
            uow.revisions.add(draft)
            uow.commit()

        published = draft.publish(published_by=ACTOR, published_at=LATER)
        with unit_of_work as uow:
            uow.revisions.save_state(published)
            uow.commit()

        with unit_of_work as uow:
            stored = uow.revisions.get(draft.revision_id)
            assert stored is not None
            assert stored.publication_state is PublicationState.PUBLISHED
            assert stored.content_digest is not None

    def test_saving_state_never_rewrites_content(self, unit_of_work: UnitOfWork) -> None:
        """The guarantee every execution record depends on."""
        task = a_task()
        original = a_revision(task).publish(published_by=ACTOR, published_at=NOW)
        with unit_of_work as uow:
            uow.tasks.add(task)
            uow.revisions.add(original)
            uow.commit()

        tampered = TaskRevision(
            revision_id=original.revision_id,
            task_id=original.task_id,
            revision_number=original.revision_number,
            action=ActionSpecification(
                executor_type=ExecutorType.SHELL,
                entrypoint="/usr/bin/bash",
                arguments=("/opt/tasks/SOMETHING_ELSE.sh",),
            ),
            created_at=original.created_at,
            created_by=original.created_by,
            publication_state=PublicationState.SUPERSEDED,
            published_at=original.published_at,
            published_by=original.published_by,
            content_digest=original.content_digest,
        )

        with unit_of_work as uow:
            uow.revisions.save_state(tampered)
            uow.commit()

        with unit_of_work as uow:
            stored = uow.revisions.get(original.revision_id)
            assert stored is not None
            assert stored.action == original.action, "content must not have been rewritten"
            assert stored.publication_state is PublicationState.SUPERSEDED

    def test_saving_state_of_a_missing_revision_raises(self, unit_of_work: UnitOfWork) -> None:
        with unit_of_work as uow, pytest.raises(NotFoundError):
            uow.revisions.save_state(a_revision(a_task()))


class TestTransactionBoundary:
    def test_an_uncommitted_block_writes_nothing(self, unit_of_work: UnitOfWork) -> None:
        task = a_task()
        with unit_of_work as uow:
            uow.tasks.add(task)
            # No commit.

        with unit_of_work as uow:
            assert uow.tasks.get(task.task_id) is None

    def test_an_exception_rolls_back(self, unit_of_work: UnitOfWork) -> None:
        task = a_task()
        boom = RuntimeError("failure after a successful write")

        with pytest.raises(RuntimeError), unit_of_work as uow:
            uow.tasks.add(task)
            raise boom

        with unit_of_work as uow:
            assert uow.tasks.get(task.task_id) is None

    def test_exceptions_are_never_suppressed(self, unit_of_work: UnitOfWork) -> None:
        """A caller must not be able to believe a failed write succeeded."""
        with pytest.raises(ValueError, match="propagated"), unit_of_work as uow:
            uow.tasks.add(a_task())
            message = "propagated"
            raise ValueError(message)

    def test_an_explicit_rollback_discards_the_work(self, unit_of_work: UnitOfWork) -> None:
        task = a_task()
        with unit_of_work as uow:
            uow.tasks.add(task)
            uow.rollback()
            uow.commit()

        with unit_of_work as uow:
            assert uow.tasks.get(task.task_id) is None

    def test_both_repositories_share_one_transaction(self, unit_of_work: UnitOfWork) -> None:
        """A task and its first revision must land together or not at all."""
        task = a_task()
        revision = a_revision(task)

        with pytest.raises(RuntimeError), unit_of_work as uow:
            uow.tasks.add(task)
            uow.revisions.add(revision)
            message = "fail before commit"
            raise RuntimeError(message)

        with unit_of_work as uow:
            assert uow.tasks.get(task.task_id) is None
            assert uow.revisions.get(revision.revision_id) is None

    def test_using_it_outside_a_block_is_an_error(self, unit_of_work: UnitOfWork) -> None:
        with pytest.raises(RuntimeError, match="context manager"):
            unit_of_work.commit()


class TestTimezoneHandling:
    def test_no_naive_datetime_reaches_the_domain(self, unit_of_work: UnitOfWork) -> None:
        task = a_task()
        with unit_of_work as uow:
            uow.tasks.add(task)
            uow.commit()

        with unit_of_work as uow:
            stored = uow.tasks.get(task.task_id)
            assert stored is not None
            assert stored.created_at.value.tzinfo is not None

    def test_timestamps_survive_a_round_trip_exactly(self, unit_of_work: UnitOfWork) -> None:
        task = a_task().update_metadata(name="Renamed", updated_by=ACTOR, updated_at=LATER)
        with unit_of_work as uow:
            uow.tasks.add(task)
            uow.commit()

        with unit_of_work as uow:
            stored = uow.tasks.get(task.task_id)
            assert stored is not None
            assert stored.created_at == NOW
            assert stored.updated_at == LATER

    def test_a_non_utc_input_is_normalised(self, unit_of_work: UnitOfWork) -> None:
        """Whatever zone a caller used, storage and retrieval agree on the instant."""
        from zoneinfo import ZoneInfo

        tokyo = UtcTimestamp(datetime(2026, 7, 27, 15, 0, tzinfo=ZoneInfo("Asia/Tokyo")))
        task = Task.create(name="Tokyo Job", owner_id=ACTOR, created_by=ACTOR, created_at=tokyo)

        with unit_of_work as uow:
            uow.tasks.add(task)
            uow.commit()

        with unit_of_work as uow:
            stored = uow.tasks.get(task.task_id)
            assert stored is not None
            assert stored.created_at == tokyo
            assert stored.created_at.value.hour == 6


class TestDatabaseConstraints:
    def test_foreign_keys_are_enforced(self, unit_of_work: UnitOfWork, engine: Engine) -> None:
        """SQLite has them off by default; a revision must not orphan itself."""
        orphan = a_revision(a_task())
        with unit_of_work as uow, pytest.raises(ConflictError):
            uow.revisions.add(orphan)
        _ = engine

    def test_a_task_with_revisions_cannot_be_deleted(
        self, unit_of_work: UnitOfWork, engine: Engine
    ) -> None:
        """RESTRICT: deleting a task must never destroy what executions refer to."""
        task = a_task()
        with unit_of_work as uow:
            uow.tasks.add(task)
            uow.revisions.add(a_revision(task))
            uow.commit()

        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text("DELETE FROM tasks WHERE task_id = :task_id"),
                {"task_id": task.task_id.to_primitive()},
            )
