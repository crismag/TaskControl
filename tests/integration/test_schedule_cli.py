"""The deployment loop an operator actually runs: plan, apply, verify.

Driven through the CLI against a real database and real files on disk, because that is the
only level at which "does this work?" has a useful answer. The unit tests prove each rule;
this proves the pieces are wired to each other.

Nothing here touches a real crontab. Cron directories are temporary, and the user crontab
is never configured, so the ``crontab`` command is never invoked.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from taskcontrol.adapters.persistence.unit_of_work import UnitOfWork

# Importing the composition root is what registers the callback that puts settings on the
# context; without it every command fails before it starts.
from taskcontrol.apps.cli import main as _composition_root  # noqa: F401
from taskcontrol.cli.commands import app
from taskcontrol.domain.common.identifiers import OwnerId, TaskRevisionId
from taskcontrol.domain.common.values import RevisionNumber, UtcTimestamp
from taskcontrol.domain.deployment.strategies import (
    DeploymentSpecification,
    DeploymentStrategy,
    DeploymentTarget,
    PeriodicClassification,
)
from taskcontrol.domain.scheduling.schedules import CronExpression
from taskcontrol.domain.tasks.actions import ActionSpecification, ExecutorType
from taskcontrol.domain.tasks.lifecycle import TaskLifecycleState
from taskcontrol.domain.tasks.revision import TaskRevision
from taskcontrol.domain.tasks.task import Task

NOW = UtcTimestamp(datetime(2026, 7, 27, 9, 0, tzinfo=UTC))
ACTOR = OwnerId.generate()

runner = CliRunner()


@pytest.fixture
def host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Configure a throwaway host layout and point the CLI at it."""
    etc = tmp_path / "etc"
    (etc / "cron.daily").mkdir(parents=True)
    (etc / "cron.d").mkdir()

    monkeypatch.setenv("TASKCONTROL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TASKCONTROL_RUN_PARTS_ROOT", str(etc))
    monkeypatch.setenv("TASKCONTROL_CRON_D_DIR", str(etc / "cron.d"))
    monkeypatch.setenv("TASKCONTROL_TASKCTL_COMMAND", "/usr/local/bin/taskctl")
    return etc


def _seed(sqlite_url: str, name: str, deployment: DeploymentSpecification, schedule: str | None):
    """Publish one active capability with a deployment specification."""
    from taskcontrol.infrastructure.database import (
        create_database_engine,
        create_session_factory,
    )

    session_factory = create_session_factory(create_database_engine(sqlite_url))
    task = Task.create(name=name, owner_id=ACTOR, created_by=ACTOR, created_at=NOW)
    revision = TaskRevision(
        revision_id=TaskRevisionId.generate(),
        task_id=task.task_id,
        revision_number=RevisionNumber(1),
        action=ActionSpecification(
            executor_type=ExecutorType.EXECUTABLE, entrypoint="/bin/echo", arguments=("hello",)
        ),
        created_at=NOW,
        created_by=ACTOR,
        deployment=deployment,
        activation_schedule=CronExpression(schedule) if schedule else None,
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


@pytest.fixture
def seeded(host: Path, tmp_path: Path) -> Path:
    """Return a host with one run-parts capability and one cron.d capability deployed."""
    assert runner.invoke(app, ["init"]).exit_code == 0
    url = f"sqlite+pysqlite:///{(tmp_path / 'data' / 'taskcontrol.db').as_posix()}"

    _seed(
        url,
        "Clean scratch volume",
        DeploymentSpecification.for_classification(PeriodicClassification.DAILY),
        None,
    )
    _seed(
        url,
        "Settlement report",
        DeploymentSpecification(
            strategy=DeploymentStrategy.CRON_D_FILE,
            target=DeploymentTarget.CRON_D,
            execution_user="settlement",
        ),
        "30 17 * * 1-5",
    )
    return host


class TestPlan:
    def test_a_plan_changes_nothing(self, seeded: Path) -> None:
        """The property the whole plan/apply split exists for."""
        result = runner.invoke(app, ["schedule", "plan"])

        assert result.exit_code == 0
        assert "CREATE" in result.output
        assert not list((seeded / "cron.daily").iterdir())
        assert not list((seeded / "cron.d").iterdir())

    def test_the_plan_names_where_each_artefact_goes(self, seeded: Path) -> None:
        """An operator must be able to see the path before anything is written to it."""
        result = runner.invoke(app, ["schedule", "plan"])

        assert "cron.daily/clean-scratch-volume" in result.output
        assert "cron.d/settlement-report" in result.output


class TestApply:
    def test_apply_deploys_both_strategies(self, seeded: Path) -> None:
        result = runner.invoke(app, ["schedule", "apply", "--yes"])

        assert result.exit_code == 0
        assert (seeded / "cron.daily" / "clean-scratch-volume").exists()
        assert (seeded / "cron.d" / "settlement-report").exists()

    def test_the_run_parts_artefact_is_executable(self, seeded: Path) -> None:
        """Cron silently ignores a run-parts script without the bit, which looks like success."""
        runner.invoke(app, ["schedule", "apply", "--yes"])

        assert (seeded / "cron.daily" / "clean-scratch-volume").stat().st_mode & 0o111

    def test_the_cron_d_file_names_the_execution_user(self, seeded: Path) -> None:
        """The reason to use cron.d at all."""
        runner.invoke(app, ["schedule", "apply", "--yes"])

        content = (seeded / "cron.d" / "settlement-report").read_text(encoding="utf-8")
        assert (
            "30 17 * * 1-5 settlement /usr/local/bin/taskctl activate settlement-report" in content
        )

    def test_reapplying_does_nothing(self, seeded: Path) -> None:
        runner.invoke(app, ["schedule", "apply", "--yes"])
        result = runner.invoke(app, ["schedule", "apply", "--yes"])

        assert result.exit_code == 0
        assert "Nothing to do" in result.output


class TestVerify:
    def test_a_freshly_applied_host_matches(self, seeded: Path) -> None:
        runner.invoke(app, ["schedule", "apply", "--yes"])
        result = runner.invoke(app, ["schedule", "verify"])

        assert result.exit_code == 0
        assert "match" in result.output

    def test_a_hand_edited_artefact_is_found_and_exits_non_zero(self, seeded: Path) -> None:
        """Exits non-zero so it can be run from monitoring, which is the point of having it."""
        runner.invoke(app, ["schedule", "apply", "--yes"])
        deployed = seeded / "cron.d" / "settlement-report"
        deployed.write_text(
            deployed.read_text(encoding="utf-8").replace("30 17", "45 17"), encoding="utf-8"
        )

        result = runner.invoke(app, ["schedule", "verify"])

        assert result.exit_code == 1
        assert "MODIFIED" in result.output

    def test_applying_repairs_drift(self, seeded: Path) -> None:
        runner.invoke(app, ["schedule", "apply", "--yes"])
        deployed = seeded / "cron.d" / "settlement-report"
        deployed.write_text(
            deployed.read_text(encoding="utf-8").replace("30 17", "45 17"), encoding="utf-8"
        )

        runner.invoke(app, ["schedule", "apply", "--yes"])

        assert runner.invoke(app, ["schedule", "verify"]).exit_code == 0


class TestStatus:
    def test_status_reports_what_would_deploy_where(self, seeded: Path) -> None:
        result = runner.invoke(app, ["schedule", "status", "--json"])

        payload = json.loads(result.output)
        by_slug = {entry["slug"]: entry for entry in payload["deployable"]}

        assert by_slug["clean-scratch-volume"]["strategy"] == "run_parts_directory"
        assert by_slug["clean-scratch-volume"]["schedule"] is None
        assert by_slug["settlement-report"]["target"] == "cron_d"
        assert by_slug["settlement-report"]["schedule"] == "30 17 * * 1-5"

    def test_a_capability_that_is_not_active_is_not_deployed(
        self, host: Path, tmp_path: Path
    ) -> None:
        """Lifecycle governs deployment: a draft capability has no business in a crontab."""
        assert runner.invoke(app, ["init"]).exit_code == 0

        result = runner.invoke(app, ["schedule", "status"])
        assert "No active capability" in result.output
