"""Two concurrent activations of one capability, in two real processes.

R1 measured the failure this way, so the fix is measured the same way. Two threads sharing a
lock object would prove nothing about cron, where every activation is a separate process and
shares no memory with any other.

The R1 result, for comparison:

```text
proc-a: succeeded    reason=None
proc-b: succeeded    reason=None
```

Both ran, with `OverlapPolicy.FORBID` in force. That is what this test now forbids.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from taskcontrol.adapters.persistence.unit_of_work import UnitOfWork
from taskcontrol.domain.common.identifiers import OwnerId, TaskRevisionId
from taskcontrol.domain.common.values import Duration, RevisionNumber, UtcTimestamp
from taskcontrol.domain.execution.results import TimeoutPolicy
from taskcontrol.domain.tasks.actions import ActionSpecification, ExecutorType
from taskcontrol.domain.tasks.lifecycle import TaskLifecycleState
from taskcontrol.domain.tasks.revision import ExecutionControls, TaskRevision
from taskcontrol.domain.tasks.task import Task

NOW = UtcTimestamp(datetime(2026, 7, 27, 2, 0, tzinfo=UTC))
ACTOR = OwnerId.generate()

# Long enough that the two processes genuinely overlap, short enough not to slow the suite.
WORK_SECONDS = 2


@pytest.fixture
def installation(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """Return a data directory and the environment a subprocess needs to use it."""
    data = tmp_path / "data"
    environment = {
        **os.environ,
        "TASKCONTROL_DATA_DIR": str(data),
        "TASKCONTROL_LOG_LEVEL": "CRITICAL",
    }
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "taskcontrol.apps.cli.main", "init"],
        env=environment,
        capture_output=True,
        check=False,
    )
    return data, environment


def _publish_slow_capability(data: Path) -> Task:
    """Publish a capability whose work takes long enough for two runs to overlap."""
    from taskcontrol.infrastructure.database import (
        create_database_engine,
        create_session_factory,
    )

    url = f"sqlite+pysqlite:///{(data / 'taskcontrol.db').as_posix()}"
    session_factory = create_session_factory(create_database_engine(url))

    task = Task.create(name="Slow overlap probe", owner_id=ACTOR, created_by=ACTOR, created_at=NOW)
    revision = TaskRevision(
        revision_id=TaskRevisionId.generate(),
        task_id=task.task_id,
        revision_number=RevisionNumber(1),
        action=ActionSpecification(
            executor_type=ExecutorType.EXECUTABLE,
            entrypoint="/bin/sleep",
            arguments=(str(WORK_SECONDS),),
        ),
        created_at=NOW,
        created_by=ACTOR,
        controls=ExecutionControls(
            timeout=TimeoutPolicy(run_timeout=Duration(60), termination_grace=Duration(5))
        ),
    ).publish(published_by=ACTOR, published_at=NOW)

    task = replace(
        task,
        lifecycle_state=TaskLifecycleState.ACTIVE,
        active_revision_id=revision.revision_id,
    )
    with UnitOfWork(session_factory) as uow:
        uow.tasks.add(task)
        uow.revisions.add(revision)
        uow.commit()
    return task


def _run_in_a_separate_process(environment: dict[str, str], slug: str) -> dict[str, object]:
    """Run one activation in its own process and return what it recorded."""
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "taskcontrol.apps.cli.main", "run", slug, "--json"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    line = next(
        (line for line in completed.stdout.splitlines() if line.startswith("{")),
        "",
    )
    return json.loads(line) if line else {"outcome": "no output", "stderr": completed.stderr}


class TestConcurrentActivation:
    """The claim R2 may not make without evidence: overlap is actually prevented."""

    def test_exactly_one_of_two_concurrent_activations_runs(
        self, installation: tuple[Path, dict[str, str]]
    ) -> None:
        """Two processes, one capability, forbid-overlap in force.

        Threads here only start the two subprocesses concurrently; the contended state is
        in two separate interpreters, which is the situation cron produces.
        """
        data, environment = installation
        _publish_slow_capability(data)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [
                future.result()
                for future in [
                    pool.submit(_run_in_a_separate_process, environment, "slow-overlap-probe")
                    for _ in range(2)
                ]
            ]

        outcomes = sorted(str(result.get("outcome")) for result in results)
        assert outcomes == ["blocked", "succeeded"], results

    def test_the_blocked_activation_says_why(
        self, installation: tuple[Path, dict[str, str]]
    ) -> None:
        """A refusal nobody can explain is barely better than an overlap.

        ADR 0016 requires a reason code on this outcome, and an operator seeing a job that
        did not run needs to know it was deliberate.
        """
        data, environment = installation
        _publish_slow_capability(data)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [
                future.result()
                for future in [
                    pool.submit(_run_in_a_separate_process, environment, "slow-overlap-probe")
                    for _ in range(2)
                ]
            ]

        blocked = next(r for r in results if r.get("outcome") == "blocked")
        assert blocked.get("reason_code") == "blocked.overlap_lock_held"
        assert "already running" in str(blocked.get("explanation"))

    def test_both_activations_are_recorded(self, installation: tuple[Path, dict[str, str]]) -> None:
        """The blocked one is a first-class execution, not a silence.

        A trigger that produces no record is a trigger nobody can investigate, which is the
        specific thing that makes an unexplained gap in cron history so expensive.
        """
        data, environment = installation
        task = _publish_slow_capability(data)

        with ThreadPoolExecutor(max_workers=2) as pool:
            [
                future.result()
                for future in [
                    pool.submit(_run_in_a_separate_process, environment, "slow-overlap-probe")
                    for _ in range(2)
                ]
            ]

        from taskcontrol.infrastructure.database import (
            create_database_engine,
            create_session_factory,
        )

        url = f"sqlite+pysqlite:///{(data / 'taskcontrol.db').as_posix()}"
        with UnitOfWork(create_session_factory(create_database_engine(url))) as uow:
            recorded = uow.executions.list_for_task(task.task_id)

        assert len(recorded) == 2
        assert all(execution.is_finished for execution in recorded)

    def test_the_capability_is_claimable_again_afterwards(
        self, installation: tuple[Path, dict[str, str]]
    ) -> None:
        """A claim that outlived its run would stop the job forever, which is worse than
        the overlap it prevents."""
        data, environment = installation
        _publish_slow_capability(data)

        with ThreadPoolExecutor(max_workers=2) as pool:
            [
                future.result()
                for future in [
                    pool.submit(_run_in_a_separate_process, environment, "slow-overlap-probe")
                    for _ in range(2)
                ]
            ]

        later = _run_in_a_separate_process(environment, "slow-overlap-probe")
        assert later.get("outcome") == "succeeded", later
