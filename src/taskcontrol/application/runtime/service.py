"""The execution runtime — one path from trigger to recorded outcome.

Every caller enters here: a cron-invoked wrapper, a queue worker, an administrative run-now,
and any transport adapter. There is deliberately no second path, because two paths would
eventually classify the same failure two different ways.

Activation never redefines execution (ADR 0025). Whatever caused the request — time arriving
or somebody asking — the work below is identical.

**The guarantee this module makes: an execution that is created reaches a terminal
persisted state.** Not "usually", and not "unless something unexpected happens". An
execution left `RUNNING` is invisible to an operator and holds its overlap lock until the
process restarts, so the terminal write happens in a ``finally`` — including when
classification itself fails, when persistence fails, and when the runtime is interrupted.
If the runtime genuinely cannot say what happened, it records `UNKNOWN`, which is honest,
rather than guessing, which is not.

Two limits apply until R2 addresses them, both recorded in
``development/reviews/R1_WAVE3_COMPATIBILITY.md``:

* This service reads the task revision from persistence before it can execute, so it cannot
  yet honour ADR 0024's availability-first activation policy — a cron wrapper must resolve
  its revision from locally deployed assets.
* Overlap protection depends on the injected lock. The Phase 1 process-local implementation
  provides none between separate activations; durable claims arrive in R2 (ADR 0023).

Expectations are **not** evaluated. `SUCCEEDED` here means the process
succeeded, nothing more. `OUTCOME_FAILED` is unreachable until Wave 4 supplies real
evidence — the seam exists and stays empty, because fabricating evidence to light up a code
path would make the record lie.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from taskcontrol.common.errors import NotFoundError, TaskControlError, ValidationError
from taskcontrol.domain.common.identifiers import AttemptId, OwnerId, TaskId
from taskcontrol.domain.common.tracing import CorrelationId, IdempotencyKey
from taskcontrol.domain.execution.execution import (
    Execution,
    ExecutionAttempt,
    TriggerSource,
)
from taskcontrol.domain.execution.vocabulary import (
    ExecutionOutcome,
    ExecutionState,
    ReasonCode,
    ReasonCodes,
)
from taskcontrol.domain.policies.classification import (
    Classification,
    classify_process_result,
    decide_retry,
)
from taskcontrol.domain.tasks.lifecycle import PublicationState
from taskcontrol.domain.tasks.revision import TaskRevision
from taskcontrol.domain.tasks.task import Task
from taskcontrol.infrastructure.logging import correlation_context, get_logger
from taskcontrol.ports.executor import ExecutionRequest, Executor
from taskcontrol.ports.lock import LockHandle, OverlapLock

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RunRequest:
    """A request to run a task once.

    Attributes:
        task_id: The task to run.
        trigger_source: What is asking.
        requested_by: Who is asking.
        correlation_id: Ties this execution's records together.
        idempotency_key: Recognises a duplicate delivery of the same request.
        environment_overrides: Extra environment for this run only.
    """

    task_id: TaskId
    trigger_source: TriggerSource = TriggerSource.MANUAL
    requested_by: OwnerId | None = None
    correlation_id: CorrelationId | None = None
    idempotency_key: IdempotencyKey | None = None
    environment_overrides: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RunResult:
    """What a run produced.

    Attributes:
        execution: The finished execution, as persisted.
        was_duplicate: Whether an idempotency key matched an existing execution, in which
            case nothing new ran and the original is returned.
    """

    execution: Execution
    was_duplicate: bool = False

    @property
    def outcome(self) -> ExecutionOutcome:
        """The terminal outcome. Always present: a returned execution has finished."""
        assert self.execution.outcome is not None  # noqa: S101 - guaranteed by the runtime
        return self.execution.outcome

    @property
    def succeeded(self) -> bool:
        """Whether the execution achieved its operational intent."""
        return self.outcome.is_success


class RuntimeService:
    """Runs a task and records what happened.

    Args:
        unit_of_work_factory: Builds a unit of work per transaction. The runtime opens
            several: an execution's progress must be visible to an operator while it runs,
            which one long transaction would prevent.
        executors: Chooses the adapter for an action.
        lock: Prevents overlapping executions. See ADR 0021 — the Phase 1 implementation
            guards a single process only.
        clock: Supplies time, injected so a decision can be reproduced.
        owner_identity: How this runtime identifies itself when holding a lock.
    """

    def __init__(
        self,
        *,
        unit_of_work_factory: Any,
        executors: Any,
        lock: OverlapLock,
        clock: Any,
        owner_identity: str = "taskcontrol-runtime",
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._executors = executors
        self._lock = lock
        self._clock = clock
        self._owner_identity = owner_identity

    def run(self, request: RunRequest) -> RunResult:
        """Run a task once and return its finished execution.

        Args:
            request: What to run.

        Returns:
            The result. The execution is always terminal.

        Raises:
            NotFoundError: If the task or its active revision does not exist.
            ValidationError: If the task is not runnable — no active revision, or an
                executor that does not exist.
        """
        task, revision = self._load(request.task_id)

        if request.idempotency_key is not None:
            existing = self._find_duplicate(request.task_id, request.idempotency_key)
            if existing is not None:
                logger.info(
                    "Returning the existing execution for a duplicate request",
                    extra={
                        "execution_id": str(existing.execution_id),
                        "idempotency_key": str(request.idempotency_key),
                    },
                )
                return RunResult(execution=existing, was_duplicate=True)

        execution = Execution.requested(
            task_id=task.task_id,
            revision_id=revision.revision_id,
            trigger_source=request.trigger_source,
            requested_at=self._clock.now(),
            correlation_id=request.correlation_id or CorrelationId.generate(),
            idempotency_key=request.idempotency_key,
            requested_by=request.requested_by,
        )
        self._persist_new(execution)

        with correlation_context(
            correlation_id=str(execution.correlation_id),
            execution_id=str(execution.execution_id),
            task_id=str(task.task_id),
        ):
            return RunResult(execution=self._execute(execution, task, revision, request))

    def _execute(
        self,
        execution: Execution,
        task: Task,
        revision: TaskRevision,
        request: RunRequest,
    ) -> Execution:
        """Take an execution from pending to terminal, whatever happens.

        The ``finally`` is the point of this method. Every path out of it — success,
        failure, an unexpected exception, an interrupt — leaves a terminal persisted
        execution.
        """
        handle: LockHandle | None = None
        finished: Execution | None = None

        try:
            execution = self._save(execution.transition_to(ExecutionState.EVALUATING))

            handle = self._acquire_lock(task.task_id, execution)
            if handle is None:
                finished = self._finish(
                    execution,
                    ExecutionOutcome.BLOCKED,
                    reason_code=ReasonCodes.BLOCKED_OVERLAP_LOCK_HELD,
                    explanation=(
                        f"Another execution of this task is already running in "
                        f"{self._lock.scope_description}."
                    ),
                )
                return finished  # noqa: RET504 - read by the finally block

            finished = self._run_attempts(execution, revision, request)
            return finished  # noqa: RET504 - read by the finally block

        except TaskControlError as exc:
            # A known failure: the runtime could not run the work, but it knows why.
            logger.exception("Execution failed before or during the runtime")
            finished = self._finish(
                execution,
                ExecutionOutcome.INFRASTRUCTURE_FAILED,
                reason_code=ReasonCodes.INFRASTRUCTURE_EXECUTOR_UNAVAILABLE,
                explanation=exc.message,
            )
            return finished  # noqa: RET504 - read by the finally block

        except BaseException:
            # Deliberately BaseException: a KeyboardInterrupt or SystemExit must not leave
            # an execution running forever. The state is unproven, so it is recorded as
            # UNKNOWN rather than guessed as failed.
            logger.exception("Execution interrupted; recording an unproven outcome")
            finished = self._finish(
                execution,
                ExecutionOutcome.UNKNOWN,
                explanation=(
                    "The runtime was interrupted and cannot prove what happened. "
                    "This execution requires reconciliation."
                ),
            )
            raise

        finally:
            if handle is not None:
                self._lock.release(handle)
            # Last line of defence. If every path above somehow failed to finish the
            # execution, it is finished here — an execution stuck in a non-terminal state
            # is invisible to an operator and holds its lock until the process restarts.
            if finished is None or not finished.is_finished:
                self._force_terminal(execution)

    def _run_attempts(
        self, execution: Execution, revision: TaskRevision, request: RunRequest
    ) -> Execution:
        """Run the action, retrying while the policy and the outcome both allow it."""
        action = revision.action
        controls = revision.controls
        executor: Executor = self._executors.get(action.executor_type)

        environment = self._resolve_environment(revision, request)
        classification: Classification | None = None

        while True:
            attempt_number = execution.attempt_count + 1
            started_at = self._clock.now()
            attempt = ExecutionAttempt(
                attempt_id=AttemptId.generate(),
                execution_id=execution.execution_id,
                attempt_number=attempt_number,
                started_at=started_at,
                executor_type=str(action.executor_type),
            )
            execution = self._save(execution.begin_attempt(attempt=attempt, started_at=started_at))

            logger.info(
                "Attempt started",
                extra={"attempt_number": attempt_number, "executor": str(action.executor_type)},
            )

            report = executor.run(
                ExecutionRequest(
                    action=action,
                    environment=environment,
                    timeout=controls.timeout.run_timeout,
                    termination_grace=controls.timeout.termination_grace,
                )
            )

            execution = self._save(
                execution.record_attempt_result(
                    attempt.finish(
                        result=report.result,
                        finished_at=self._clock.now(),
                        stdout=report.output.stdout,
                        stderr=report.output.stderr,
                    )
                )
            )

            # Wave 3 passes no expectation evidence. SUCCEEDED means the process
            # succeeded; OUTCOME_FAILED is unreachable until Wave 4 evaluates real
            # evidence (blueprint Wave 4).
            classification = classify_process_result(report.result)

            logger.info(
                "Attempt finished",
                extra={
                    "attempt_number": attempt_number,
                    "outcome": str(classification.outcome),
                    "reason_code": (
                        classification.reason_code.to_primitive()
                        if classification.reason_code
                        else None
                    ),
                    "duration_seconds": report.result.duration.to_primitive(),
                },
            )

            retry = decide_retry(
                classification.outcome,
                policy=controls.retry,
                attempts_made=execution.attempt_count,
            )
            if not retry.should_retry:
                return self._finish(
                    execution,
                    classification.outcome,
                    reason_code=classification.reason_code,
                    explanation=f"{classification.explanation} {retry.reason}".strip(),
                )

            logger.info("Retrying", extra={"reason": retry.reason})

    def _resolve_environment(self, revision: TaskRevision, request: RunRequest) -> dict[str, str]:
        """Build the environment the process will see.

        Wave 3 resolves literal bindings only. A secret reference is deliberately **not**
        materialised: the secrets adapter arrives later, and inventing a resolution now
        would either invent a value or silently drop the binding. Instead the run fails
        with an explanation.

        Raises:
            ValidationError: If the revision needs a secret this wave cannot resolve.
        """
        secrets = revision.action.secret_references
        if secrets:
            raise ValidationError(
                "This revision references secrets, and secret resolution is not available "
                "in this build. Running it would either invent a value or silently drop "
                "the binding.",
                details={"secret_references": [str(reference) for reference in secrets]},
            )

        environment = {
            binding.name: binding.value
            for binding in revision.action.environment
            if binding.value is not None
        }
        environment.update(request.environment_overrides)
        return environment

    def _acquire_lock(self, task_id: TaskId, execution: Execution) -> LockHandle | None:
        """Take the overlap lock, or report that another execution holds it."""
        return self._lock.try_acquire(
            task_id, owner=f"{self._owner_identity}:{execution.execution_id}"
        )

    def _load(self, task_id: TaskId) -> tuple[Task, TaskRevision]:
        """Load a task and the revision that governs its executions.

        Raises:
            NotFoundError: If the task or its active revision is missing.
            ValidationError: If the task has no active revision, or that revision is not
                published.
        """
        with self._unit_of_work_factory() as uow:
            task = uow.tasks.get(task_id)
            if task is None:
                raise NotFoundError("Task not found.", details={"task_id": str(task_id)})
            if task.active_revision_id is None:
                raise ValidationError(
                    "This task has no active revision, so there is nothing to run. "
                    "Publish and activate a revision first.",
                    details={"task_id": str(task_id), "state": str(task.lifecycle_state)},
                )
            revision = uow.revisions.get(task.active_revision_id)
            if revision is None:
                raise NotFoundError(
                    "The task's active revision does not exist.",
                    details={"revision_id": str(task.active_revision_id)},
                )
            if revision.publication_state is PublicationState.DRAFT:
                raise ValidationError(
                    "A draft revision cannot be executed. Publish it first.",
                    details={"revision_id": str(revision.revision_id)},
                )
        return task, revision

    def _find_duplicate(self, task_id: TaskId, key: IdempotencyKey) -> Execution | None:
        """Return an execution a previous identical request already created."""
        with self._unit_of_work_factory() as uow:
            found: Execution | None = uow.executions.find_by_idempotency_key(task_id, key)
        return found

    def _persist_new(self, execution: Execution) -> None:
        """Store a newly created execution."""
        with self._unit_of_work_factory() as uow:
            uow.executions.add(execution)
            uow.commit()

    def _save(self, execution: Execution) -> Execution:
        """Persist an execution's current state.

        Each save is its own transaction. A single long one would hide an execution's
        progress from every other reader until it finished, which defeats the point of
        recording progress at all.
        """
        with self._unit_of_work_factory() as uow:
            uow.executions.save(execution)
            uow.commit()
        return execution

    def _finish(
        self,
        execution: Execution,
        outcome: ExecutionOutcome,
        *,
        reason_code: ReasonCode | None = None,
        explanation: str = "",
    ) -> Execution:
        """Bring an execution to its terminal state and persist it."""
        finished = execution.finish(
            outcome=outcome,
            finished_at=self._clock.now(),
            reason_code=reason_code,
            explanation=explanation,
        )
        logger.info(
            "Execution finished",
            extra={
                "outcome": str(outcome),
                "reason_code": reason_code.to_primitive() if reason_code else None,
                "attempts": finished.attempt_count,
            },
        )
        return self._save(finished)

    def _force_terminal(self, execution: Execution) -> None:
        """Finish an execution that escaped every other path.

        Best effort and deliberately silent about its own failures: this runs inside a
        ``finally``, and raising here would replace the original error with a persistence
        error, hiding what actually went wrong.
        """
        try:
            with self._unit_of_work_factory() as uow:
                current = uow.executions.get(execution.execution_id)
                if current is None or current.is_finished:
                    return
                uow.executions.save(
                    current.finish(
                        outcome=ExecutionOutcome.UNKNOWN,
                        finished_at=self._clock.now(),
                        explanation=(
                            "The runtime exited without recording an outcome. This "
                            "execution requires reconciliation."
                        ),
                    )
                )
                uow.commit()
            logger.error(
                "Execution forced to a terminal state by the runtime's cleanup path",
                extra={"execution_id": str(execution.execution_id)},
            )
        except Exception:  # noqa: BLE001 - cleanup must not mask the original failure
            logger.exception(
                "Could not force an execution to a terminal state",
                extra={"execution_id": str(execution.execution_id)},
            )
