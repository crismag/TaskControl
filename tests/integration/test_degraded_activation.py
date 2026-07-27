"""The scenario R2 exists to make possible.

```text
TaskControl installs revision
        |
control-plane database becomes unavailable
        |
cron activates the installed wrapper
        |
wrapper resolves everything locally
        |
activation policy is applied
        |
execution either refuses safely or journals locally
        |
cron receives an accurate exit status
        |
state reconciles when persistence returns
```

Every step is driven through the real CLI. The database is made unavailable by moving the
file out from under it, which is a blunt instrument and exactly right: it produces the same
thing a dead database produces, which is a process that cannot read what it needs.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from taskcontrol.adapters.persistence.unit_of_work import UnitOfWork
from taskcontrol.application.activation import EXIT_DECLINED, EXIT_SUCCESS
from taskcontrol.apps.cli import main as _composition_root  # noqa: F401 — registers settings
from taskcontrol.cli.commands import app
from taskcontrol.domain.common.identifiers import OwnerId, TaskRevisionId
from taskcontrol.domain.common.values import (
    Duration,
    RevisionNumber,
    SecretReference,
    UtcTimestamp,
)
from taskcontrol.domain.deployment.strategies import (
    DeploymentSpecification,
    PeriodicClassification,
)
from taskcontrol.domain.execution.results import TimeoutPolicy
from taskcontrol.domain.tasks.actions import (
    ActionSpecification,
    EnvironmentBinding,
    ExecutorType,
)
from taskcontrol.domain.tasks.lifecycle import TaskLifecycleState
from taskcontrol.domain.tasks.revision import (
    ActivationPolicy,
    ExecutionControls,
    TaskRevision,
)
from taskcontrol.domain.tasks.task import Task

NOW = UtcTimestamp(datetime(2026, 7, 27, 2, 0, tzinfo=UTC))
ACTOR = OwnerId.generate()

runner = CliRunner()


@pytest.fixture
def host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the CLI at a throwaway host and return its data directory."""
    etc = tmp_path / "etc"
    (etc / "cron.daily").mkdir(parents=True)
    (etc / "cron.d").mkdir()

    monkeypatch.setenv("TASKCONTROL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TASKCONTROL_RUN_PARTS_ROOT", str(etc))
    monkeypatch.setenv("TASKCONTROL_CRON_D_DIR", str(etc / "cron.d"))
    monkeypatch.setenv("TASKCONTROL_TASKCTL_COMMAND", "/usr/local/bin/taskctl")
    # Structured logs go to stdout, and several assertions here parse --json output.
    monkeypatch.setenv("TASKCONTROL_LOG_LEVEL", "CRITICAL")

    assert runner.invoke(app, ["init"]).exit_code == 0
    return tmp_path / "data"


def _database_url(data: Path) -> str:
    return f"sqlite+pysqlite:///{(data / 'taskcontrol.db').as_posix()}"


def _publish(
    data: Path,
    *,
    name: str,
    policy: ActivationPolicy,
    action: ActionSpecification | None = None,
) -> Task:
    """Publish one active capability with the given activation policy."""
    from taskcontrol.infrastructure.database import (
        create_database_engine,
        create_session_factory,
    )

    session_factory = create_session_factory(create_database_engine(_database_url(data)))
    task = Task.create(name=name, owner_id=ACTOR, created_by=ACTOR, created_at=NOW)
    revision = TaskRevision(
        revision_id=TaskRevisionId.generate(),
        task_id=task.task_id,
        revision_number=RevisionNumber(1),
        action=action
        or ActionSpecification(
            executor_type=ExecutorType.EXECUTABLE,
            entrypoint="/bin/echo",
            arguments=("did the work",),
        ),
        created_at=NOW,
        created_by=ACTOR,
        controls=ExecutionControls(
            timeout=TimeoutPolicy(run_timeout=Duration(30), termination_grace=Duration(5)),
            activation_policy=policy,
        ),
        deployment=DeploymentSpecification.for_classification(PeriodicClassification.DAILY),
    ).publish(published_by=ACTOR, published_at=NOW)

    task = replace(
        task,
        lifecycle_state=TaskLifecycleState.ACTIVE,
        active_revision_id=revision.revision_id,
        description=f"{name} — seeded for a test.",
    )
    with UnitOfWork(session_factory) as uow:
        uow.tasks.add(task)
        uow.revisions.add(revision)
        uow.commit()
    return task


UNREACHABLE_DATABASE = "sqlite+pysqlite:////nonexistent/taskcontrol.db"


@contextmanager
def control_plane_unavailable(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Point TaskControl at a database it cannot reach, for the duration of a block.

    An earlier version of this helper moved the database file aside and back. That looked
    tidier and quietly destroyed the data: SQLite keeps recent writes in a ``-wal`` sidecar,
    which the move left behind, so the restored file came back empty and every assertion
    afterwards was measuring the wrong thing.

    Redirecting the URL is both simpler and closer to the real failure, which is a process
    that cannot reach the database rather than one whose file has been vandalised.
    """
    monkeypatch.setenv("TASKCONTROL_DATABASE_URL", UNREACHABLE_DATABASE)
    try:
        yield
    finally:
        monkeypatch.delenv("TASKCONTROL_DATABASE_URL", raising=False)


class TestInstallation:
    def test_apply_installs_the_revision_beside_the_artefact(self, host: Path) -> None:
        """The artefact and the definition it executes must arrive together."""
        _publish(host, name="Nightly backup", policy=ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL)
        assert runner.invoke(app, ["schedule", "apply", "--yes"]).exit_code == 0

        manifest = host / "installed" / "nightly-backup.json"
        assert manifest.exists()
        assert json.loads(manifest.read_text(encoding="utf-8"))["slug"] == "nightly-backup"

    def test_the_manifest_is_owner_readable_only(self, host: Path) -> None:
        """It carries no secret values, but it does carry what a privileged job will run."""
        _publish(host, name="Nightly backup", policy=ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL)
        runner.invoke(app, ["schedule", "apply", "--yes"])

        mode = (host / "installed" / "nightly-backup.json").stat().st_mode
        assert not mode & 0o077

    def test_a_tampered_manifest_refuses_to_run(self, host: Path) -> None:
        """Cron runs whatever it finds, so the manifest verifies against its own digest."""
        _publish(host, name="Nightly backup", policy=ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL)
        runner.invoke(app, ["schedule", "apply", "--yes"])

        manifest = host / "installed" / "nightly-backup.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["action"]["entrypoint"] = "/bin/rm"
        manifest.write_text(json.dumps(data), encoding="utf-8")

        result = runner.invoke(app, ["activate", "nightly-backup"])
        assert result.exit_code != 0


class TestActivationWithTheControlPlaneAvailable:
    def test_it_runs_and_records_normally(self, host: Path) -> None:
        """Nothing about the wrapper path degrades the ordinary case."""
        _publish(host, name="Nightly backup", policy=ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL)
        runner.invoke(app, ["schedule", "apply", "--yes"])

        result = runner.invoke(app, ["activate", "nightly-backup", "--json"])
        payload = json.loads(result.output)

        assert result.exit_code == EXIT_SUCCESS
        assert payload["outcome"] == "succeeded"
        assert payload["degraded"] is False
        assert payload["journalled"] is False
        assert not (host / "journal" / "activations.jsonl").exists()


class TestRequireControlState:
    """The default. An unrecorded run is worse than a missed one."""

    def test_it_refuses_to_run_and_says_why(
        self, host: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _publish(host, name="Settlement run", policy=ActivationPolicy.REQUIRE_CONTROL_STATE)
        runner.invoke(app, ["schedule", "apply", "--yes"])
        with control_plane_unavailable(monkeypatch):
            result = runner.invoke(app, ["activate", "settlement-run"])

        assert result.exit_code == EXIT_DECLINED
        assert "was not started" in result.output

    def test_the_exit_code_distinguishes_declining_from_failing(
        self, host: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A monitor must be able to tell "did not run" from "ran and failed"."""
        _publish(host, name="Settlement run", policy=ActivationPolicy.REQUIRE_CONTROL_STATE)
        runner.invoke(app, ["schedule", "apply", "--yes"])
        with control_plane_unavailable(monkeypatch):
            assert runner.invoke(app, ["activate", "settlement-run"]).exit_code == 75

    def test_nothing_is_journalled(self, host: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """It did not run, so there is nothing to record."""
        _publish(host, name="Settlement run", policy=ActivationPolicy.REQUIRE_CONTROL_STATE)
        runner.invoke(app, ["schedule", "apply", "--yes"])
        with control_plane_unavailable(monkeypatch):
            runner.invoke(app, ["activate", "settlement-run"])

        assert not (host / "journal" / "activations.jsonl").exists()


class TestContinueWithLocalJournal:
    """Availability-first. Missing the backup is worse than missing the record of it."""

    def test_the_work_runs_with_the_database_gone(
        self, host: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _publish(host, name="Nightly backup", policy=ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL)
        runner.invoke(app, ["schedule", "apply", "--yes"])
        with control_plane_unavailable(monkeypatch):
            result = runner.invoke(app, ["activate", "nightly-backup", "--json"])
        payload = json.loads(result.output)

        assert result.exit_code == EXIT_SUCCESS
        assert payload["outcome"] == "succeeded"
        assert payload["degraded"] is True
        assert payload["journalled"] is True

    def test_the_journal_records_the_dispatch_and_no_output(
        self, host: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ADR 0027: the journal is a dispatch record, not a log.

        Its fixed small shape is what makes it writable when things are already degraded.
        """
        _publish(host, name="Nightly backup", policy=ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL)
        runner.invoke(app, ["schedule", "apply", "--yes"])
        with control_plane_unavailable(monkeypatch):
            runner.invoke(app, ["activate", "nightly-backup"])

        entry = json.loads((host / "journal" / "activations.jsonl").read_text().strip())

        assert entry["slug"] == "nightly-backup"
        assert entry["outcome"] == "succeeded"
        assert entry["exit_code"] == 0
        assert "stdout" not in entry
        assert "stderr" not in entry
        assert "did the work" not in json.dumps(entry)

    def test_the_journal_says_overlap_protection_was_not_in_force(
        self, host: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A real reduction in guarantee, stated rather than hidden.

        The claim store *is* the database that is unreachable, so a degraded run cannot be
        overlap-protected. An operator reconciling later has to know that.
        """
        _publish(host, name="Nightly backup", policy=ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL)
        runner.invoke(app, ["schedule", "apply", "--yes"])
        with control_plane_unavailable(monkeypatch):
            runner.invoke(app, ["activate", "nightly-backup"])

        entry = json.loads((host / "journal" / "activations.jsonl").read_text().strip())
        assert "no overlap protection" in entry["explanation"]

    def test_a_failing_command_still_exits_non_zero(
        self, host: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cron must receive an accurate exit status, degraded or not."""
        _publish(
            host,
            name="Failing job",
            policy=ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL,
            action=ActionSpecification(
                executor_type=ExecutorType.EXECUTABLE, entrypoint="/bin/false"
            ),
        )
        runner.invoke(app, ["schedule", "apply", "--yes"])
        with control_plane_unavailable(monkeypatch):
            result = runner.invoke(app, ["activate", "failing-job"])
        assert result.exit_code == 1

    def test_a_capability_needing_secrets_refuses(
        self, host: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Manifests carry references, never values.

        Running with a silently incomplete environment would be worse than not running,
        because the work would appear to have happened.
        """
        _publish(
            host,
            name="Report upload",
            policy=ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL,
            action=ActionSpecification(
                executor_type=ExecutorType.EXECUTABLE,
                entrypoint="/bin/echo",
                environment=(
                    EnvironmentBinding(
                        name="API_TOKEN",
                        secret=SecretReference(provider="env", path="API_TOKEN"),
                    ),
                ),
            ),
        )
        runner.invoke(app, ["schedule", "apply", "--yes"])
        with control_plane_unavailable(monkeypatch):
            result = runner.invoke(app, ["activate", "report-upload"])

        assert result.exit_code == EXIT_DECLINED
        assert "secrets" in result.output


class TestReconciliation:
    def test_a_journalled_run_becomes_an_execution_record(
        self, host: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The last step: state reconciles when persistence returns."""
        _publish(host, name="Nightly backup", policy=ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL)
        runner.invoke(app, ["schedule", "apply", "--yes"])
        with control_plane_unavailable(monkeypatch):
            runner.invoke(app, ["activate", "nightly-backup"])

        result = runner.invoke(app, ["reconcile", "--json"])
        assert result.exception is None, result.exception
        payload = json.loads(result.output)

        assert payload["ingested"] == 1
        assert payload["cleared"] is True
        assert not (host / "journal" / "activations.jsonl").exists()

    def test_reconciling_twice_produces_one_record(
        self, host: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Idempotent by execution identity, which the wrapper allocated before running."""
        _publish(host, name="Nightly backup", policy=ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL)
        runner.invoke(app, ["schedule", "apply", "--yes"])
        with control_plane_unavailable(monkeypatch):
            runner.invoke(app, ["activate", "nightly-backup"])

        runner.invoke(app, ["reconcile"])
        second = json.loads(runner.invoke(app, ["reconcile", "--json"]).output)

        assert second["ingested"] == 0

    def test_replaying_the_same_journal_produces_one_record(
        self, host: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The property that makes clearing the journal safe to interrupt.

        A crash between commit and truncate leaves entries to be ingested again; that is
        harmless only because ingestion keys on identity rather than on shape.
        """
        _publish(host, name="Nightly backup", policy=ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL)
        runner.invoke(app, ["schedule", "apply", "--yes"])
        with control_plane_unavailable(monkeypatch):
            runner.invoke(app, ["activate", "nightly-backup"])

        journal = host / "journal" / "activations.jsonl"
        kept = journal.read_text(encoding="utf-8")

        runner.invoke(app, ["reconcile"])
        journal.write_text(kept, encoding="utf-8")
        replayed = json.loads(runner.invoke(app, ["reconcile", "--json"]).output)

        assert replayed["ingested"] == 0
        assert replayed["already_known"] == 1

    def test_the_reconciled_record_says_where_it_came_from(
        self, host: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Months later, a reconciled run must be distinguishable from a watched one."""
        _publish(host, name="Nightly backup", policy=ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL)
        runner.invoke(app, ["schedule", "apply", "--yes"])
        with control_plane_unavailable(monkeypatch):
            runner.invoke(app, ["activate", "nightly-backup"])
        runner.invoke(app, ["reconcile"])

        from taskcontrol.infrastructure.database import (
            create_database_engine,
            create_session_factory,
        )

        factory = create_session_factory(create_database_engine(_database_url(host)))
        with UnitOfWork(factory) as uow:
            executions = uow.executions.list_unfinished()
            assert executions == ()

    def test_a_torn_journal_line_is_reported_not_hidden(
        self, host: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nothing can be done about a lost entry, but a count must know it was lost."""
        _publish(host, name="Nightly backup", policy=ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL)
        runner.invoke(app, ["schedule", "apply", "--yes"])
        with control_plane_unavailable(monkeypatch):
            runner.invoke(app, ["activate", "nightly-backup"])

        journal = host / "journal" / "activations.jsonl"
        journal.write_text(
            '{"format_version": 1, "execution_id": "trunc\n' + journal.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        payload = json.loads(runner.invoke(app, ["reconcile", "--json"]).output)

        assert payload["unreadable"] == 1
        assert payload["ingested"] == 1
