"""Migrations and restart durability — Wave 2's gate.

The gate is a test that creates a database, migrates it, writes through the application,
drops every connection as a process exit would, reopens it, and reads the data back. That
is the whole claim of this wave: **definitions and history survive a restart.**
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine, inspect, text

from taskcontrol.adapters.persistence.unit_of_work import UnitOfWork
from taskcontrol.common.errors import PermanentInfrastructureError
from taskcontrol.domain.common import (
    Duration,
    OwnerId,
    RevisionNumber,
    TaskRevisionId,
    UtcTimestamp,
)
from taskcontrol.domain.execution import TimeoutPolicy
from taskcontrol.domain.tasks import (
    ActionSpecification,
    ExecutionControls,
    ExecutorType,
    PublicationState,
    Task,
    TaskLifecycleState,
    TaskRevision,
)
from taskcontrol.infrastructure.database import create_database_engine, create_session_factory
from taskcontrol.infrastructure.migrations import (
    current_revision,
    downgrade_to,
    head_revision,
    is_up_to_date,
    upgrade_to_head,
)

pytestmark = pytest.mark.integration

NOW = UtcTimestamp(datetime(2026, 7, 27, 6, 0, tzinfo=UTC))
ACTOR = OwnerId.generate()

EXPECTED_TABLES = {"tasks", "task_revisions", "alembic_version"}


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    """Return a path for a fresh SQLite database file."""
    return tmp_path / "restart.db"


def url_for(path: Path) -> str:
    """Return a SQLite URL for a path."""
    return f"sqlite+pysqlite:///{path.as_posix()}"


def a_published_task() -> tuple[Task, TaskRevision]:
    """Build an active task with a published revision."""
    task = Task.create(
        name="Daily Settlement Report",
        owner_id=ACTOR,
        created_by=ACTOR,
        created_at=NOW,
        description="Generate the settlement reconciliation report.",
        labels=frozenset({"finance", "critical"}),
    )
    revision = TaskRevision(
        revision_id=TaskRevisionId.generate(),
        task_id=task.task_id,
        revision_number=RevisionNumber.first(),
        action=ActionSpecification(
            executor_type=ExecutorType.SHELL,
            entrypoint="/usr/bin/bash",
            arguments=("/opt/tasks/report.sh",),
            working_directory="/opt/tasks",
        ),
        created_at=NOW,
        created_by=ACTOR,
        controls=ExecutionControls(timeout=TimeoutPolicy(run_timeout=Duration(1200))),
        change_summary="Initial published definition.",
    ).publish(published_by=ACTOR, published_at=NOW)
    task = task.activate_revision(revision.revision_id, updated_by=ACTOR, updated_at=NOW)
    return task, revision


class TestMigrationLifecycle:
    def test_upgrade_creates_every_table(self, database_path: Path) -> None:
        engine = create_database_engine(url_for(database_path))
        try:
            upgrade_to_head(engine)
            assert set(inspect(engine).get_table_names()) >= EXPECTED_TABLES
        finally:
            engine.dispose()

    def test_upgrade_reaches_head(self, database_path: Path) -> None:
        engine = create_database_engine(url_for(database_path))
        try:
            upgrade_to_head(engine)
            assert current_revision(engine) == head_revision(engine)
            assert is_up_to_date(engine)
        finally:
            engine.dispose()

    def test_a_fresh_database_is_not_up_to_date(self, database_path: Path) -> None:
        """Readiness depends on this being false before init runs."""
        engine = create_database_engine(url_for(database_path))
        try:
            assert current_revision(engine) is None
            assert not is_up_to_date(engine)
        finally:
            engine.dispose()

    def test_upgrading_twice_is_a_no_op(self, database_path: Path) -> None:
        """`taskctl init` is also the upgrade command, so it must be safe to repeat."""
        engine = create_database_engine(url_for(database_path))
        try:
            first = upgrade_to_head(engine)
            second = upgrade_to_head(engine)
            assert first == second
        finally:
            engine.dispose()

    def test_downgrade_on_an_empty_database(self, database_path: Path) -> None:
        engine = create_database_engine(url_for(database_path))
        try:
            upgrade_to_head(engine)
            downgrade_to(engine, "base")
            remaining = set(inspect(engine).get_table_names())
            assert "tasks" not in remaining
            assert "task_revisions" not in remaining
            assert current_revision(engine) is None
        finally:
            engine.dispose()

    def test_downgrade_on_a_populated_database(self, database_path: Path) -> None:
        """Reversibility must hold with data present, not only on an empty schema."""
        engine = create_database_engine(url_for(database_path))
        try:
            upgrade_to_head(engine)
            task, revision = a_published_task()
            with UnitOfWork(create_session_factory(engine)) as uow:
                uow.tasks.add(task)
                uow.revisions.add(revision)
                uow.commit()

            downgrade_to(engine, "base")
            assert "tasks" not in set(inspect(engine).get_table_names())
        finally:
            engine.dispose()

    def test_upgrade_downgrade_upgrade_round_trips(self, database_path: Path) -> None:
        engine = create_database_engine(url_for(database_path))
        try:
            upgrade_to_head(engine)
            downgrade_to(engine, "base")
            assert upgrade_to_head(engine) == head_revision(engine)
            assert set(inspect(engine).get_table_names()) >= EXPECTED_TABLES
        finally:
            engine.dispose()

    def test_a_failing_migration_reports_without_leaking_the_url(self, database_path: Path) -> None:
        """A database URL may embed a password and must never reach an error message."""
        engine = create_database_engine(url_for(database_path))
        try:
            upgrade_to_head(engine)
            with engine.begin() as connection:
                connection.execute(text("UPDATE alembic_version SET version_num = 'nonexistent'"))

            with pytest.raises(PermanentInfrastructureError) as caught:
                upgrade_to_head(engine)
            assert str(database_path) not in f"{caught.value.message} {caught.value.details}"
        finally:
            engine.dispose()


class TestRestartDurability:
    """The wave gate: create, migrate, write, restart, read back."""

    def test_definitions_survive_a_restart(self, database_path: Path) -> None:
        task, revision = a_published_task()

        # --- First process: initialise and write. ---
        first_engine = create_database_engine(url_for(database_path))
        upgrade_to_head(first_engine)
        with UnitOfWork(create_session_factory(first_engine)) as uow:
            uow.tasks.add(task)
            uow.revisions.add(revision)
            uow.commit()

        # --- Process exit: every connection is dropped. ---
        first_engine.dispose()
        del first_engine

        # --- Second process: a completely new engine over the same file. ---
        second_engine = create_database_engine(url_for(database_path))
        try:
            assert is_up_to_date(second_engine), "the schema must already be current"

            with UnitOfWork(create_session_factory(second_engine)) as uow:
                stored_task = uow.tasks.get(task.task_id)
                stored_revision = uow.revisions.get(revision.revision_id)

            assert stored_task == task
            assert stored_revision == revision
        finally:
            second_engine.dispose()

    def test_a_restart_preserves_publication_state_and_digest(self, database_path: Path) -> None:
        task, revision = a_published_task()

        engine = create_database_engine(url_for(database_path))
        upgrade_to_head(engine)
        with UnitOfWork(create_session_factory(engine)) as uow:
            uow.tasks.add(task)
            uow.revisions.add(revision)
            uow.commit()
        engine.dispose()

        reopened = create_database_engine(url_for(database_path))
        try:
            with UnitOfWork(create_session_factory(reopened)) as uow:
                stored = uow.revisions.get(revision.revision_id)

            assert stored is not None
            assert stored.publication_state is PublicationState.PUBLISHED
            assert stored.content_digest == revision.content_digest
            assert stored.compute_digest() == stored.content_digest, (
                "the stored content must still match the digest it was published with"
            )
        finally:
            reopened.dispose()

    def test_a_restart_preserves_task_state_and_labels(self, database_path: Path) -> None:
        task, revision = a_published_task()

        engine = create_database_engine(url_for(database_path))
        upgrade_to_head(engine)
        with UnitOfWork(create_session_factory(engine)) as uow:
            uow.tasks.add(task)
            uow.revisions.add(revision)
            uow.commit()
        engine.dispose()

        reopened = create_database_engine(url_for(database_path))
        try:
            with UnitOfWork(create_session_factory(reopened)) as uow:
                stored = uow.tasks.get(task.task_id)

            assert stored is not None
            assert stored.lifecycle_state is TaskLifecycleState.ACTIVE
            assert stored.active_revision_id == revision.revision_id
            assert stored.labels == frozenset({"finance", "critical"})
        finally:
            reopened.dispose()

    def test_an_uncommitted_write_does_not_survive_a_restart(self, database_path: Path) -> None:
        """A crash mid-transaction must lose the partial write, not half of it."""
        task, _ = a_published_task()

        engine = create_database_engine(url_for(database_path))
        upgrade_to_head(engine)
        with UnitOfWork(create_session_factory(engine)) as uow:
            uow.tasks.add(task)
            # No commit — the process "dies" here.
        engine.dispose()

        reopened = create_database_engine(url_for(database_path))
        try:
            with UnitOfWork(create_session_factory(reopened)) as uow:
                assert uow.tasks.get(task.task_id) is None
        finally:
            reopened.dispose()

    def test_the_storage_version_survives_a_restart(self, database_path: Path) -> None:
        """Optimistic concurrency must keep working across a restart."""
        task, revision = a_published_task()

        engine = create_database_engine(url_for(database_path))
        upgrade_to_head(engine)
        with UnitOfWork(create_session_factory(engine)) as uow:
            uow.tasks.add(task)
            uow.revisions.add(revision)
            uow.commit()
        with UnitOfWork(create_session_factory(engine)) as uow:
            version = uow.tasks.version_of(task.task_id)
            assert version is not None
            uow.tasks.update(
                task.update_metadata(name="Renamed", updated_by=ACTOR, updated_at=NOW),
                expected_version=version,
            )
            uow.commit()
        engine.dispose()

        reopened = create_database_engine(url_for(database_path))
        try:
            with UnitOfWork(create_session_factory(reopened)) as uow:
                assert uow.tasks.version_of(task.task_id) == version + 1
        finally:
            reopened.dispose()


class TestSqliteConfiguration:
    def test_foreign_keys_are_enabled(self, database_path: Path) -> None:
        """SQLite disables them by default, which would let a revision orphan itself."""
        engine = create_database_engine(url_for(database_path))
        try:
            with engine.connect() as connection:
                assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
        finally:
            engine.dispose()

    def test_write_ahead_logging_is_enabled(self, database_path: Path) -> None:
        """WAL lets the API read while the runtime writes."""
        engine = create_database_engine(url_for(database_path))
        try:
            with engine.connect() as connection:
                mode = connection.execute(text("PRAGMA journal_mode")).scalar()
            assert str(mode).lower() == "wal"
        finally:
            engine.dispose()

    def test_a_busy_timeout_is_configured(self, database_path: Path) -> None:
        """The API and the runtime will contend routinely; failing instantly is wrong."""
        engine = create_database_engine(url_for(database_path))
        try:
            with engine.connect() as connection:
                timeout = connection.execute(text("PRAGMA busy_timeout")).scalar()
            assert timeout is not None
            assert int(timeout) > 0
        finally:
            engine.dispose()


class TestSchemaMatchesModels:
    def test_migrated_columns_match_the_models(self, engine: Engine) -> None:
        """A migration that drifts from the models is a release-day outage."""
        from taskcontrol.adapters.persistence.models import Base

        inspector = inspect(engine)
        for table_name, table in Base.metadata.tables.items():
            migrated = {column["name"] for column in inspector.get_columns(table_name)}
            declared = {column.name for column in table.columns}
            assert declared == migrated, f"{table_name} columns drifted"

    def test_migrated_indexes_match_the_models(self, engine: Engine) -> None:
        from taskcontrol.adapters.persistence.models import Base

        inspector = inspect(engine)
        for table_name, table in Base.metadata.tables.items():
            migrated = {index["name"] for index in inspector.get_indexes(table_name)}
            declared = {index.name for index in table.indexes}
            assert declared <= migrated, f"{table_name} is missing a declared index"
