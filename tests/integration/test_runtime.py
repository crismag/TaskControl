"""The runtime, exercised against real subprocesses and a real database.

Wave 3's gate. Every assertion here runs an actual process — a mocked executor would prove
the orchestration is self-consistent while saying nothing about whether TaskControl can
kill a process that ignores SIGTERM.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine

from taskcontrol.adapters.clock import SystemClock
from taskcontrol.adapters.executors import default_registry
from taskcontrol.adapters.locking import ProcessLocalOverlapLock
from taskcontrol.adapters.persistence.unit_of_work import UnitOfWork
from taskcontrol.application.runtime import RunRequest, RuntimeService
from taskcontrol.common.errors import NotFoundError, ValidationError
from taskcontrol.domain.common import (
    Duration,
    IdempotencyKey,
    OwnerId,
    RevisionNumber,
    SecretReference,
    TaskId,
    TaskRevisionId,
    UtcTimestamp,
)
from taskcontrol.domain.execution import (
    ExecutionOutcome,
    ExecutionState,
    ReasonCodes,
    RetryPolicy,
    TimeoutPolicy,
    TriggerSource,
)
from taskcontrol.domain.tasks import (
    ActionSpecification,
    EnvironmentBinding,
    ExecutionControls,
    ExecutorType,
    Task,
    TaskRevision,
)
from taskcontrol.infrastructure.database import create_session_factory

pytestmark = pytest.mark.integration

NOW = UtcTimestamp(datetime(2026, 7, 27, 6, 0, tzinfo=UTC))
OWNER = OwnerId.generate()

SECRET_CANARY = "sup3r-s3cret-canary-value-9f2b"  # noqa: S105 - a canary, not a credential
"""Planted where a leak would show. Any appearance outside the process environment fails."""


def no_delay_retry(max_attempts: int) -> RetryPolicy:
    """A retry policy with no backoff, so tests do not sleep."""
    return RetryPolicy(max_attempts=max_attempts, base_delay=Duration(0), max_delay=Duration(0))


@pytest.fixture
def runtime(engine: Engine) -> RuntimeService:
    """Build a runtime over a migrated database."""
    session_factory = create_session_factory(engine)
    return RuntimeService(
        unit_of_work_factory=lambda: UnitOfWork(session_factory),
        executors=default_registry(),
        lock=ProcessLocalOverlapLock(),
        clock=SystemClock(),
    )


@pytest.fixture
def store(engine: Engine) -> UnitOfWork:
    """A unit of work for arranging and inspecting state."""
    return UnitOfWork(create_session_factory(engine))


def seed(
    store: UnitOfWork,
    action: ActionSpecification,
    *,
    controls: ExecutionControls | None = None,
    name: str = "Runtime Test Task",
) -> TaskId:
    """Create an active task with a published revision."""
    task = Task.create(name=name, owner_id=OWNER, created_by=OWNER, created_at=NOW)
    revision = TaskRevision(
        revision_id=TaskRevisionId.generate(),
        task_id=task.task_id,
        revision_number=RevisionNumber.first(),
        action=action,
        created_at=NOW,
        created_by=OWNER,
        controls=controls or ExecutionControls(),
    ).publish(published_by=OWNER, published_at=NOW)
    task = task.activate_revision(revision.revision_id, updated_by=OWNER, updated_at=NOW)

    with store as uow:
        uow.tasks.add(task)
        uow.revisions.add(revision)
        uow.commit()
    return task.task_id


def shell(script: str) -> ActionSpecification:
    """Build a shell action running a script."""
    return ActionSpecification(
        executor_type=ExecutorType.SHELL, entrypoint="/bin/sh", arguments=("-c", script)
    )


class TestOutcomes:
    """Each acceptance case produces the correct ADR 0016 outcome and reason code."""

    def test_success(self, runtime: RuntimeService, store: UnitOfWork) -> None:
        task_id = seed(store, shell("echo done"))
        result = runtime.run(RunRequest(task_id=task_id))

        assert result.outcome is ExecutionOutcome.SUCCEEDED
        assert result.succeeded
        assert result.execution.attempts[0].stdout.strip() == "done"

    def test_non_zero_exit(self, runtime: RuntimeService, store: UnitOfWork) -> None:
        task_id = seed(store, shell("exit 7"))
        result = runtime.run(RunRequest(task_id=task_id))

        assert result.outcome is ExecutionOutcome.FAILED
        assert result.execution.attempts[0].result is not None
        assert result.execution.attempts[0].result.exit_code == 7

    def test_launch_failure(self, runtime: RuntimeService, store: UnitOfWork) -> None:
        """A missing binary is a failure of the launch, not of the work."""
        task_id = seed(
            store,
            ActionSpecification(
                executor_type=ExecutorType.EXECUTABLE, entrypoint="/usr/bin/definitely-absent"
            ),
        )
        result = runtime.run(RunRequest(task_id=task_id))

        assert result.outcome is ExecutionOutcome.LAUNCH_FAILED

    def test_timeout_with_termination(self, runtime: RuntimeService, store: UnitOfWork) -> None:
        task_id = seed(
            store,
            shell("sleep 30"),
            controls=ExecutionControls(
                timeout=TimeoutPolicy(run_timeout=Duration(1), termination_grace=Duration(1))
            ),
        )
        result = runtime.run(RunRequest(task_id=task_id))

        assert result.outcome is ExecutionOutcome.TIMED_OUT
        assert result.execution.reason_code == ReasonCodes.TIMED_OUT_RUN_TIMEOUT_EXCEEDED

    def test_a_process_ignoring_sigterm_is_killed(
        self, runtime: RuntimeService, store: UnitOfWork
    ) -> None:
        """An unstoppable task would hold its overlap lock forever."""
        task_id = seed(
            store,
            shell("trap '' TERM; sleep 30"),
            controls=ExecutionControls(
                timeout=TimeoutPolicy(run_timeout=Duration(1), termination_grace=Duration(1))
            ),
        )
        result = runtime.run(RunRequest(task_id=task_id))

        assert result.outcome is ExecutionOutcome.TIMED_OUT
        attempt = result.execution.attempts[0]
        assert attempt.result is not None
        assert attempt.result.signal_number == 9, "SIGKILL should have been required"

    def test_stdout_and_stderr_stay_separate(
        self, runtime: RuntimeService, store: UnitOfWork
    ) -> None:
        """Interleaving loses the distinction between a result and a diagnostic."""
        task_id = seed(store, shell("echo to-stdout; echo to-stderr >&2"))
        result = runtime.run(RunRequest(task_id=task_id))

        attempt = result.execution.attempts[0]
        assert attempt.stdout.strip() == "to-stdout"
        assert attempt.stderr.strip() == "to-stderr"


class TestRetries:
    def test_each_attempt_is_a_separate_persisted_record(
        self, runtime: RuntimeService, store: UnitOfWork
    ) -> None:
        """ "It eventually worked" and "it worked first time" must be distinguishable."""
        task_id = seed(
            store,
            shell("exit 1"),
            controls=ExecutionControls(retry=no_delay_retry(3)),
        )
        result = runtime.run(RunRequest(task_id=task_id))

        assert result.execution.attempt_count == 3
        assert [a.attempt_number for a in result.execution.attempts] == [1, 2, 3]

        with store as uow:
            stored = uow.executions.get(result.execution.execution_id)
        assert stored is not None
        assert stored.attempt_count == 3

    def test_retries_stop_at_the_configured_limit(
        self, runtime: RuntimeService, store: UnitOfWork
    ) -> None:
        task_id = seed(
            store,
            shell("exit 1"),
            controls=ExecutionControls(retry=no_delay_retry(2)),
        )
        result = runtime.run(RunRequest(task_id=task_id))

        assert result.execution.attempt_count == 2
        assert result.outcome is ExecutionOutcome.FAILED

    def test_success_does_not_retry(self, runtime: RuntimeService, store: UnitOfWork) -> None:
        task_id = seed(
            store,
            shell("exit 0"),
            controls=ExecutionControls(retry=no_delay_retry(5)),
        )
        assert runtime.run(RunRequest(task_id=task_id)).execution.attempt_count == 1

    def test_a_timeout_is_not_retried_without_opting_in(
        self, runtime: RuntimeService, store: UnitOfWork
    ) -> None:
        """Re-running work that may have applied side effects must be deliberate."""
        task_id = seed(
            store,
            shell("sleep 30"),
            controls=ExecutionControls(
                timeout=TimeoutPolicy(run_timeout=Duration(1), termination_grace=Duration(1)),
                retry=no_delay_retry(3),
            ),
        )
        assert runtime.run(RunRequest(task_id=task_id)).execution.attempt_count == 1


class TestOverlapLocking:
    """Same-process contention — the only guarantee Phase 1 makes (ADR 0021)."""

    def test_contention_produces_blocked_with_its_reason_code(
        self, engine: Engine, store: UnitOfWork
    ) -> None:
        lock = ProcessLocalOverlapLock()
        session_factory = create_session_factory(engine)
        runtime = RuntimeService(
            unit_of_work_factory=lambda: UnitOfWork(session_factory),
            executors=default_registry(),
            lock=lock,
            clock=SystemClock(),
        )
        task_id = seed(store, shell("echo hi"))

        # Hold the lock as another execution in this process would.
        held = lock.try_acquire(task_id, owner="another-execution")
        assert held is not None

        result = runtime.run(RunRequest(task_id=task_id))

        assert result.outcome is ExecutionOutcome.BLOCKED
        assert result.execution.reason_code == ReasonCodes.BLOCKED_OVERLAP_LOCK_HELD
        assert result.execution.attempt_count == 0, "a blocked execution never ran"

    def test_the_blocked_explanation_states_the_lock_scope(
        self, engine: Engine, store: UnitOfWork
    ) -> None:
        """An operator must not mistake this for a cluster-wide guarantee."""
        lock = ProcessLocalOverlapLock()
        session_factory = create_session_factory(engine)
        runtime = RuntimeService(
            unit_of_work_factory=lambda: UnitOfWork(session_factory),
            executors=default_registry(),
            lock=lock,
            clock=SystemClock(),
        )
        task_id = seed(store, shell("echo hi"))
        lock.try_acquire(task_id, owner="another-execution")

        result = runtime.run(RunRequest(task_id=task_id))

        assert "process" in result.execution.explanation

    def test_the_lock_is_released_after_a_run(
        self, runtime: RuntimeService, store: UnitOfWork
    ) -> None:
        task_id = seed(store, shell("echo hi"))
        runtime.run(RunRequest(task_id=task_id))
        assert runtime.run(RunRequest(task_id=task_id)).succeeded

    def test_the_lock_is_released_after_a_failure(
        self, runtime: RuntimeService, store: UnitOfWork
    ) -> None:
        """A leaked lock would block the task until the process restarts."""
        task_id = seed(store, shell("exit 1"))
        runtime.run(RunRequest(task_id=task_id))
        second = runtime.run(RunRequest(task_id=task_id))
        assert second.outcome is ExecutionOutcome.FAILED, "not BLOCKED — the lock was freed"


class TestTerminalStateGuarantee:
    """Every launched execution finishes in a terminal persisted state."""

    def test_a_successful_execution_is_persisted_terminal(
        self, runtime: RuntimeService, store: UnitOfWork
    ) -> None:
        task_id = seed(store, shell("echo hi"))
        result = runtime.run(RunRequest(task_id=task_id))

        with store as uow:
            stored = uow.executions.get(result.execution.execution_id)
        assert stored is not None
        assert stored.state is ExecutionState.FINISHED
        assert stored.outcome is not None

    def test_no_execution_is_left_unfinished(
        self, runtime: RuntimeService, store: UnitOfWork
    ) -> None:
        """The invariant, checked across every kind of ending."""
        scripts = ["exit 0", "exit 3", "sleep 30", "trap '' TERM; sleep 30"]
        controls = ExecutionControls(
            timeout=TimeoutPolicy(run_timeout=Duration(1), termination_grace=Duration(1))
        )
        for index, script in enumerate(scripts):
            task_id = seed(store, shell(script), controls=controls, name=f"Task {index}")
            runtime.run(RunRequest(task_id=task_id))

        with store as uow:
            assert uow.executions.list_unfinished() == ()

    def test_a_blocked_execution_is_terminal_too(self, engine: Engine, store: UnitOfWork) -> None:
        lock = ProcessLocalOverlapLock()
        session_factory = create_session_factory(engine)
        runtime = RuntimeService(
            unit_of_work_factory=lambda: UnitOfWork(session_factory),
            executors=default_registry(),
            lock=lock,
            clock=SystemClock(),
        )
        task_id = seed(store, shell("echo hi"))
        lock.try_acquire(task_id, owner="other")
        runtime.run(RunRequest(task_id=task_id))

        with store as uow:
            assert uow.executions.list_unfinished() == ()

    def test_an_execution_survives_a_restart(
        self, runtime: RuntimeService, store: UnitOfWork
    ) -> None:
        """History is the product; it must outlive the process that made it."""
        task_id = seed(store, shell("echo persisted"))
        result = runtime.run(RunRequest(task_id=task_id))

        with store as uow:
            reloaded = uow.executions.get(result.execution.execution_id)

        assert reloaded is not None
        assert reloaded.outcome is ExecutionOutcome.SUCCEEDED
        assert reloaded.attempts[0].stdout.strip() == "persisted"


class TestSecretSafety:
    def test_the_parent_environment_does_not_leak_into_a_task(
        self, runtime: RuntimeService, store: UnitOfWork, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A task must not read whatever secrets are in the TaskControl process."""
        monkeypatch.setenv("TC_LEAK_CANARY", SECRET_CANARY)
        task_id = seed(store, shell("env"))

        result = runtime.run(RunRequest(task_id=task_id))

        assert SECRET_CANARY not in result.execution.attempts[0].stdout

    def test_a_canary_never_reaches_the_stored_execution(
        self, runtime: RuntimeService, store: UnitOfWork, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TC_LEAK_CANARY", SECRET_CANARY)
        task_id = seed(store, shell("env; echo done"))
        result = runtime.run(RunRequest(task_id=task_id))

        with store as uow:
            stored = uow.executions.get(result.execution.execution_id)

        assert stored is not None
        assert SECRET_CANARY not in str(stored.to_primitive())

    def test_an_unresolvable_secret_reference_fails_loudly(
        self, runtime: RuntimeService, store: UnitOfWork
    ) -> None:
        """Better to refuse than to invent a value or silently drop the binding."""
        task_id = seed(
            store,
            ActionSpecification(
                executor_type=ExecutorType.SHELL,
                entrypoint="/bin/sh",
                arguments=("-c", "echo hi"),
                environment=(
                    EnvironmentBinding("TOKEN", secret=SecretReference.parse("env://TOKEN")),
                ),
            ),
        )
        result = runtime.run(RunRequest(task_id=task_id))

        assert result.outcome is ExecutionOutcome.INFRASTRUCTURE_FAILED
        assert "secret" in result.execution.explanation.lower()

    def test_literal_environment_bindings_reach_the_process(
        self, runtime: RuntimeService, store: UnitOfWork
    ) -> None:
        task_id = seed(
            store,
            ActionSpecification(
                executor_type=ExecutorType.SHELL,
                entrypoint="/bin/sh",
                arguments=("-c", "echo $REGION"),
                environment=(EnvironmentBinding("REGION", value="eu-west-1"),),
            ),
        )
        result = runtime.run(RunRequest(task_id=task_id))

        assert result.execution.attempts[0].stdout.strip() == "eu-west-1"


class TestArgumentSafety:
    def test_arguments_are_data_not_instructions(
        self, runtime: RuntimeService, store: UnitOfWork
    ) -> None:
        """The injection that argument vectors exist to prevent."""
        marker = "/tmp/taskcontrol-injection-canary"  # noqa: S108 - deliberate, checked below
        task_id = seed(
            store,
            ActionSpecification(
                executor_type=ExecutorType.EXECUTABLE,
                entrypoint="/bin/echo",
                arguments=(f"hello; touch {marker}",),
            ),
        )
        runtime.run(RunRequest(task_id=task_id))

        assert not Path(marker).exists(), "the argument was executed as a command"


class TestIdempotency:
    def test_a_repeated_request_returns_the_original_execution(
        self, runtime: RuntimeService, store: UnitOfWork
    ) -> None:
        """A duplicate trigger delivery must not run the work twice."""
        task_id = seed(store, shell("echo once"))
        key = IdempotencyKey("delivery-42")

        first = runtime.run(RunRequest(task_id=task_id, idempotency_key=key))
        second = runtime.run(RunRequest(task_id=task_id, idempotency_key=key))

        assert second.was_duplicate
        assert second.execution.execution_id == first.execution.execution_id

        with store as uow:
            assert len(uow.executions.list_for_task(task_id)) == 1

    def test_requests_without_a_key_each_run(
        self, runtime: RuntimeService, store: UnitOfWork
    ) -> None:
        task_id = seed(store, shell("echo hi"))
        runtime.run(RunRequest(task_id=task_id))
        runtime.run(RunRequest(task_id=task_id))

        with store as uow:
            assert len(uow.executions.list_for_task(task_id)) == 2


class TestRunnability:
    def test_an_unknown_task_is_reported(self, runtime: RuntimeService) -> None:
        with pytest.raises(NotFoundError):
            runtime.run(RunRequest(task_id=TaskId.generate()))

    def test_a_task_without_an_active_revision_cannot_run(
        self, runtime: RuntimeService, store: UnitOfWork
    ) -> None:
        task = Task.create(name="Draft Only", owner_id=OWNER, created_by=OWNER, created_at=NOW)
        with store as uow:
            uow.tasks.add(task)
            uow.commit()

        with pytest.raises(ValidationError, match="no active revision"):
            runtime.run(RunRequest(task_id=task.task_id))


class TestExecutionRecord:
    def test_the_revision_is_pinned_at_creation(
        self, runtime: RuntimeService, store: UnitOfWork
    ) -> None:
        """A revision activated mid-run must not change what this execution meant."""
        task_id = seed(store, shell("echo hi"))
        result = runtime.run(RunRequest(task_id=task_id))

        with store as uow:
            task = uow.tasks.get(task_id)
        assert task is not None
        assert result.execution.revision_id == task.active_revision_id

    def test_the_trigger_source_is_recorded(
        self, runtime: RuntimeService, store: UnitOfWork
    ) -> None:
        """ "Why did this run at 3am" is a different question from "what did it do"."""
        task_id = seed(store, shell("echo hi"))
        result = runtime.run(RunRequest(task_id=task_id, trigger_source=TriggerSource.SCHEDULE))
        assert result.execution.trigger_source is TriggerSource.SCHEDULE

    def test_a_correlation_id_is_always_present(
        self, runtime: RuntimeService, store: UnitOfWork
    ) -> None:
        task_id = seed(store, shell("echo hi"))
        assert runtime.run(RunRequest(task_id=task_id)).execution.correlation_id is not None
