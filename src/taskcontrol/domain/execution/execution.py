"""Execution and ExecutionAttempt — the record of what actually happened.

An **Execution** is one evaluation of a trigger. It exists whether or not a process ever
ran: a skipped execution, a blocked execution, and a successful execution are all
executions, and all three are recorded. That is the product's founding claim expressed as
storage.

An **ExecutionAttempt** is one try within an execution. A task that fails and is retried
twice has one execution and three attempts, each with its own process result and its own
timing — so "it eventually worked" and "it worked first time" are distinguishable.

The invariant this module exists to protect: **every execution that starts must reach a
terminal state.** An execution left `RUNNING` forever is invisible to an operator and holds
its overlap lock indefinitely. The type refuses to be terminal without an outcome, and the
runtime's cleanup path is obliged to finish one honestly — as `UNKNOWN` if it genuinely
cannot say.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Self

from taskcontrol.common.errors import DomainRuleViolationError, ValidationError
from taskcontrol.domain.common.identifiers import (
    AttemptId,
    ExecutionId,
    OwnerId,
    TaskId,
    TaskRevisionId,
)
from taskcontrol.domain.common.tracing import CorrelationId, IdempotencyKey
from taskcontrol.domain.common.values import ContentDigest, Duration, UtcTimestamp
from taskcontrol.domain.execution.results import ProcessResult
from taskcontrol.domain.execution.vocabulary import (
    ExecutionOutcome,
    ExecutionState,
    ReasonCode,
    assert_legal_transition,
)

MAX_EXPLANATION_LENGTH = 4000


class TriggerSource(StrEnum):
    """What caused this execution to be considered.

    Recorded because "why did this run at 3am?" is a different question from "what did it
    do", and an operator needs both.

    This is the **activation mechanism**, recorded as provenance. No domain logic may branch
    on it: recurring and on-demand activation produce the same execution (ADR 0025).
    """

    MANUAL = "manual"
    "A person asked for it, through the CLI."

    SCHEDULE = "schedule"
    "Cron activated a managed artefact: it is now time to run this capability."

    API = "api"
    "An external system requested it through a transport — REST, MCP, or another adapter."

    RETRY = "retry"
    "A previous attempt failed and the retry policy asked for another."


@dataclass(frozen=True, slots=True)
class ExecutionAttempt:
    """One try within an execution.

    Attributes:
        attempt_id: Stable identifier.
        execution_id: The execution this belongs to.
        attempt_number: 1-based position within the execution.
        started_at: When the attempt began.
        finished_at: When it ended. ``None`` while in flight.
        result: What the process did. ``None`` while in flight.
        stdout: Captured standard output.
        stderr: Captured standard error, kept separate from stdout.
        executor_type: Which adapter ran it.
    """

    attempt_id: AttemptId
    execution_id: ExecutionId
    attempt_number: int
    started_at: UtcTimestamp
    executor_type: str
    finished_at: UtcTimestamp | None = None
    result: ProcessResult | None = None
    stdout: str = ""
    stderr: str = ""

    def __post_init__(self) -> None:
        """Validate the attempt.

        Raises:
            ValidationError: If numbering is wrong or the finish state is inconsistent.
        """
        if self.attempt_number < 1:
            raise ValidationError(
                "Attempt numbers start at 1.",
                details={"attempt_number": self.attempt_number},
            )
        if (self.finished_at is None) != (self.result is None):
            raise ValidationError(
                "An attempt has either both a finish time and a result, or neither. "
                "One without the other describes a state that cannot exist.",
                details={"attempt_id": str(self.attempt_id)},
            )

    @property
    def is_finished(self) -> bool:
        """Whether this attempt has ended."""
        return self.result is not None

    @property
    def duration(self) -> Duration:
        """How long the attempt ran, zero while still in flight."""
        return self.result.duration if self.result else Duration(0)

    def finish(
        self, *, result: ProcessResult, finished_at: UtcTimestamp, stdout: str, stderr: str
    ) -> Self:
        """Record how this attempt ended.

        Args:
            result: What the process did.
            finished_at: When it ended.
            stdout: Captured standard output.
            stderr: Captured standard error.

        Returns:
            The finished attempt.

        Raises:
            DomainRuleViolationError: If the attempt has already finished. An attempt's
                result is written once; rewriting it would change history.
        """
        if self.is_finished:
            raise DomainRuleViolationError(
                "This attempt has already finished. Retries create a new attempt.",
                details={"attempt_id": str(self.attempt_id)},
            )
        return replace(self, result=result, finished_at=finished_at, stdout=stdout, stderr=stderr)

    def to_primitive(self) -> dict[str, Any]:
        """Return a stable representation."""
        return {
            "attempt_id": self.attempt_id.to_primitive(),
            "execution_id": self.execution_id.to_primitive(),
            "attempt_number": self.attempt_number,
            "executor_type": self.executor_type,
            "started_at": self.started_at.to_primitive(),
            "finished_at": self.finished_at.to_primitive() if self.finished_at else None,
            "duration_seconds": self.duration.to_primitive(),
            "exit_code": self.result.exit_code if self.result else None,
            "signal_number": self.result.signal_number if self.result else None,
            "termination": str(self.result.termination) if self.result else None,
            "termination_cause": (str(self.result.termination_cause) if self.result else None),
            "stdout_bytes": self.result.stdout_bytes if self.result else 0,
            "stderr_bytes": self.result.stderr_bytes if self.result else 0,
            "output_truncated": self.result.output_truncated if self.result else False,
        }


@dataclass(frozen=True, slots=True)
class Execution:
    """One evaluation of a trigger, recorded whether or not anything ran.

    Attributes:
        execution_id: Stable identifier.
        task_id: The task being executed.
        revision_id: The exact revision that governs this execution. Pinned at creation so
            a revision activated mid-run cannot change what this execution meant.
        trigger_source: What caused it.
        requested_at: When it was requested.
        state: Where it is now.
        outcome: How it ended. Required once finished, absent before.
        reason_code: Why, for outcomes that carry one.
        explanation: A human-readable sentence, safe to display.
        attempts: Every attempt made, in order.
        started_at: When the first attempt began.
        finished_at: When the execution reached its terminal state.
        correlation_id: Ties every record produced while handling this execution.
        idempotency_key: Recognises a duplicate trigger delivery.
        requested_by: Who or what asked.
        configuration_digest: Fingerprint of the resolved configuration used.
    """

    execution_id: ExecutionId
    task_id: TaskId
    revision_id: TaskRevisionId
    trigger_source: TriggerSource
    requested_at: UtcTimestamp
    state: ExecutionState = ExecutionState.PENDING
    outcome: ExecutionOutcome | None = None
    reason_code: ReasonCode | None = None
    explanation: str = ""
    attempts: tuple[ExecutionAttempt, ...] = ()
    started_at: UtcTimestamp | None = None
    finished_at: UtcTimestamp | None = None
    correlation_id: CorrelationId | None = None
    idempotency_key: IdempotencyKey | None = None
    requested_by: OwnerId | None = None
    configuration_digest: ContentDigest | None = field(default=None)

    def __post_init__(self) -> None:
        """Validate the execution's internal consistency.

        Raises:
            ValidationError: If the state and outcome contradict each other, or a reason
                code is missing where one is required.
        """
        if self.state.requires_outcome and self.outcome is None:
            raise ValidationError(
                "A finished execution must record its outcome. An execution that ends "
                "without one is invisible to an operator.",
                details={"execution_id": str(self.execution_id)},
            )
        if not self.state.requires_outcome and self.outcome is not None:
            raise ValidationError(
                "Only a finished execution carries an outcome.",
                details={
                    "execution_id": str(self.execution_id),
                    "state": str(self.state),
                },
            )
        if self.outcome is not None and self.outcome.requires_reason_code:
            if self.reason_code is None:
                raise ValidationError(
                    f"Outcome {self.outcome} requires a reason code; without one the "
                    "result cannot be explained.",
                    details={"execution_id": str(self.execution_id)},
                )
            if not self.reason_code.matches(self.outcome):
                raise ValidationError(
                    "The reason code does not belong to this outcome.",
                    details={
                        "outcome": str(self.outcome),
                        "reason_code": self.reason_code.to_primitive(),
                    },
                )
        if len(self.explanation) > MAX_EXPLANATION_LENGTH:
            raise ValidationError(
                "Execution explanation is too long.",
                details={"maximum": MAX_EXPLANATION_LENGTH},
            )

    @classmethod
    def requested(
        cls,
        *,
        task_id: TaskId,
        revision_id: TaskRevisionId,
        trigger_source: TriggerSource,
        requested_at: UtcTimestamp,
        execution_id: ExecutionId | None = None,
        correlation_id: CorrelationId | None = None,
        idempotency_key: IdempotencyKey | None = None,
        requested_by: OwnerId | None = None,
    ) -> Self:
        """Create a pending execution.

        The record exists from the moment a trigger is considered, before any decision is
        made about whether to run. A trigger that produces no record is a trigger nobody
        can investigate.

        Args:
            task_id: The task.
            revision_id: The revision that governs this execution.
            trigger_source: What caused it.
            requested_at: When.
            execution_id: Explicit identifier, generated when omitted.
            correlation_id: Ties this execution's records together.
            idempotency_key: Recognises duplicate delivery.
            requested_by: Who asked.

        Returns:
            The pending execution.
        """
        return cls(
            execution_id=execution_id or ExecutionId.generate(),
            task_id=task_id,
            revision_id=revision_id,
            trigger_source=trigger_source,
            requested_at=requested_at,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            requested_by=requested_by,
        )

    @property
    def is_finished(self) -> bool:
        """Whether this execution has reached a terminal state."""
        return self.state.is_terminal

    @property
    def attempt_count(self) -> int:
        """How many attempts have been made."""
        return len(self.attempts)

    @property
    def latest_attempt(self) -> ExecutionAttempt | None:
        """The most recent attempt, or ``None`` when nothing ran."""
        return self.attempts[-1] if self.attempts else None

    @property
    def ran(self) -> bool:
        """Whether any process was launched for this execution."""
        return bool(self.attempts)

    def transition_to(self, state: ExecutionState) -> Self:
        """Move to another non-terminal state.

        Args:
            state: The state to move to.

        Returns:
            The execution in its new state.

        Raises:
            DomainRuleViolationError: If the transition is illegal, or if it would finish
                the execution without an outcome — use :meth:`finish` for that.
        """
        assert_legal_transition(self.state, state)
        if state.requires_outcome:
            raise DomainRuleViolationError(
                "Finish an execution with finish(), which requires an outcome.",
                details={"execution_id": str(self.execution_id)},
            )
        return replace(self, state=state)

    def begin_attempt(self, *, attempt: ExecutionAttempt, started_at: UtcTimestamp) -> Self:
        """Record that an attempt has started.

        Args:
            attempt: The attempt beginning.
            started_at: When the first attempt began, recorded once.

        Returns:
            The running execution.

        Raises:
            DomainRuleViolationError: If the execution has already finished, or the attempt
                is numbered wrongly.
        """
        if self.is_finished:
            raise DomainRuleViolationError(
                "A finished execution cannot start another attempt.",
                details={"execution_id": str(self.execution_id)},
            )
        expected = self.attempt_count + 1
        if attempt.attempt_number != expected:
            raise DomainRuleViolationError(
                "Attempts are numbered consecutively from 1.",
                details={"expected": expected, "received": attempt.attempt_number},
            )

        return replace(
            self,
            state=ExecutionState.RUNNING,
            attempts=(*self.attempts, attempt),
            started_at=self.started_at or started_at,
        )

    def record_attempt_result(self, attempt: ExecutionAttempt) -> Self:
        """Replace the latest attempt with its finished form.

        Args:
            attempt: The finished attempt.

        Returns:
            The execution with the attempt's result recorded.

        Raises:
            DomainRuleViolationError: If the attempt does not belong to this execution.
        """
        if not self.attempts or self.attempts[-1].attempt_id != attempt.attempt_id:
            raise DomainRuleViolationError(
                "Only the latest attempt of this execution can be updated.",
                details={"attempt_id": str(attempt.attempt_id)},
            )
        return replace(self, attempts=(*self.attempts[:-1], attempt))

    def request_cancellation(self) -> Self:
        """Mark that cancellation has been requested.

        Args:
            None.

        Returns:
            The execution in ``CANCELLING``.

        Raises:
            DomainRuleViolationError: If the execution is not running.
        """
        assert_legal_transition(self.state, ExecutionState.CANCELLING)
        return replace(self, state=ExecutionState.CANCELLING)

    def finish(
        self,
        *,
        outcome: ExecutionOutcome,
        finished_at: UtcTimestamp,
        reason_code: ReasonCode | None = None,
        explanation: str = "",
    ) -> Self:
        """Bring the execution to its terminal state.

        Args:
            outcome: How it ended.
            finished_at: When.
            reason_code: Why, required for outcomes that carry one.
            explanation: A human-readable sentence.

        Returns:
            The finished execution.

        Raises:
            DomainRuleViolationError: If it has already finished.
            ValidationError: If the outcome requires a reason code and none was given.
        """
        if self.is_finished:
            raise DomainRuleViolationError(
                "This execution has already finished. Its outcome is immutable.",
                details={
                    "execution_id": str(self.execution_id),
                    "outcome": str(self.outcome),
                },
            )
        assert_legal_transition(self.state, ExecutionState.FINISHED)

        return replace(
            self,
            state=ExecutionState.FINISHED,
            outcome=outcome,
            reason_code=reason_code,
            explanation=explanation,
            finished_at=finished_at,
        )

    def to_primitive(self) -> dict[str, Any]:
        """Return a stable representation."""
        return {
            "execution_id": self.execution_id.to_primitive(),
            "task_id": self.task_id.to_primitive(),
            "revision_id": self.revision_id.to_primitive(),
            "trigger_source": str(self.trigger_source),
            "state": str(self.state),
            "outcome": str(self.outcome) if self.outcome else None,
            "reason_code": self.reason_code.to_primitive() if self.reason_code else None,
            "explanation": self.explanation,
            "requested_at": self.requested_at.to_primitive(),
            "started_at": self.started_at.to_primitive() if self.started_at else None,
            "finished_at": self.finished_at.to_primitive() if self.finished_at else None,
            "attempt_count": self.attempt_count,
            "correlation_id": (self.correlation_id.to_primitive() if self.correlation_id else None),
            "idempotency_key": (
                self.idempotency_key.to_primitive() if self.idempotency_key else None
            ),
            "requested_by": self.requested_by.to_primitive() if self.requested_by else None,
            "configuration_digest": (
                self.configuration_digest.to_primitive() if self.configuration_digest else None
            ),
            "attempts": [attempt.to_primitive() for attempt in self.attempts],
        }
