"""Execution lifecycle states, terminal outcomes, and reason codes.

This module is the sole authority for the execution vocabulary, fixed by **ADR 0016**. No
other module may define an execution status vocabulary, and no other module may restate
these members.

The central product claim lives here: skip, block, launch failure, process failure,
outcome failure, timeout, cancellation, infrastructure failure, and unproven state are
different things and stay different at every visible surface.

Two enums, not one. A running execution and a finished execution answer different
questions, so ``ExecutionState`` describes where an execution is and ``ExecutionOutcome``
describes how it ended. ``outcome`` is ``None`` until the state is ``FINISHED``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Self

from taskcontrol.common.errors import ValidationError


class ExecutionState(StrEnum):
    """Where an execution currently is.

    Values are ``lower_snake_case`` on every wire, per ADR 0016.
    """

    PENDING = "pending"
    "Execution record created; not yet evaluated."

    EVALUATING = "evaluating"
    "Run conditions and dependencies are being evaluated."

    RUNNING = "running"
    "At least one attempt is in flight."

    CANCELLING = "cancelling"
    "Cancellation requested; termination in progress."

    FINISHED = "finished"
    "Terminal. ``outcome`` is set and immutable."

    @property
    def is_terminal(self) -> bool:
        """Whether no further transition is possible."""
        return self is ExecutionState.FINISHED

    @property
    def requires_outcome(self) -> bool:
        """Whether an execution in this state must carry a terminal outcome."""
        return self.is_terminal


class ExecutionOutcome(StrEnum):
    """How a finished execution ended.

    Never map a non-zero exit to a generic failure when the cause is known, and never
    convert an unproven state into success or failure — ``UNKNOWN`` is a legitimate,
    required answer.
    """

    SUCCEEDED = "succeeded"
    "Process succeeded and every required expectation passed."

    FAILED = "failed"
    "Process started and returned a failing technical result."

    LAUNCH_FAILED = "launch_failed"
    "Process could not be started: missing binary, bad working directory, permission denied."

    OUTCOME_FAILED = "outcome_failed"
    "Process result was technically acceptable but a required expectation failed."

    TIMED_OUT = "timed_out"
    "Runtime exceeded its timeout and the termination policy completed."

    CANCELLED = "cancelled"
    "An authorised cancellation prevented normal completion."

    SKIPPED = "skipped"
    "Policy deliberately declined to run: the task was not applicable now."

    BLOCKED = "blocked"
    "Applicable, but a guard prevented starting: lock held, dependency unmet, hold, approval."

    CONDITION_ERROR = "condition_error"
    "Eligibility could not be determined; the guard itself failed."

    INFRASTRUCTURE_FAILED = "infrastructure_failed"
    "Executor, target, storage, or control-plane failure prevented reliable completion."

    UNKNOWN = "unknown"
    "Final state cannot be proven and requires reconciliation."

    @property
    def is_success(self) -> bool:
        """Whether the execution achieved its operational intent.

        Only ``SUCCEEDED`` qualifies. A zero exit code with a failed required expectation
        is ``OUTCOME_FAILED``, and a skip is not a success.
        """
        return self is ExecutionOutcome.SUCCEEDED

    @property
    def ran(self) -> bool:
        """Whether a process was actually started.

        Distinguishes "did not run" from "ran and did not work", which is the difference
        between a scheduling question and an operational incident.
        """
        return self in _OUTCOMES_THAT_RAN

    @property
    def requires_reason_code(self) -> bool:
        """Whether this outcome is meaningless without a reason code."""
        return self in _OUTCOMES_REQUIRING_REASON

    @property
    def permits_reason_code(self) -> bool:
        """Whether a reason code may be recorded against this outcome (ADR 0020)."""
        return self in _OUTCOMES_PERMITTING_REASON

    @property
    def retry_eligibility(self) -> RetryEligibility:
        """Whether retrying this outcome is permitted, forbidden, or policy-dependent."""
        return _RETRY_ELIGIBILITY[self]


class RetryEligibility(StrEnum):
    """Whether an outcome may be retried.

    Eligibility is not obligation: ``BY_POLICY`` means the task's retry policy decides,
    because the operation may have side effects that make a blind retry unsafe.
    """

    NEVER = "never"
    "Retrying is always wrong. A skip did not fail; a cancellation was intentional."

    ALWAYS = "always"
    "The failure is technical and a retry is a reasonable response."

    BY_POLICY = "by_policy"
    "The task must opt in, because the work may have partially applied side effects."


_OUTCOMES_THAT_RAN: Final[frozenset[ExecutionOutcome]] = frozenset(
    {
        ExecutionOutcome.SUCCEEDED,
        ExecutionOutcome.FAILED,
        ExecutionOutcome.OUTCOME_FAILED,
        ExecutionOutcome.TIMED_OUT,
        ExecutionOutcome.CANCELLED,
    }
)

_OUTCOMES_REQUIRING_REASON: Final[frozenset[ExecutionOutcome]] = frozenset(
    {
        ExecutionOutcome.SKIPPED,
        ExecutionOutcome.BLOCKED,
        ExecutionOutcome.CONDITION_ERROR,
        ExecutionOutcome.INFRASTRUCTURE_FAILED,
        # ADR 0020: a timeout and a cancellation both end a running process, and only the
        # reason code says which — the operating system cannot tell them apart.
        ExecutionOutcome.TIMED_OUT,
        ExecutionOutcome.CANCELLED,
    }
)

_OUTCOMES_PERMITTING_REASON: Final[frozenset[ExecutionOutcome]] = _OUTCOMES_REQUIRING_REASON | {
    # Optional: a process that simply exits non-zero has no cause beyond its exit status.
    # When it was killed by a signal TaskControl did not send, that cause is knowable and
    # a code is expected.
    ExecutionOutcome.FAILED,
}

_RETRY_ELIGIBILITY: Final[dict[ExecutionOutcome, RetryEligibility]] = {
    ExecutionOutcome.SUCCEEDED: RetryEligibility.NEVER,
    ExecutionOutcome.FAILED: RetryEligibility.ALWAYS,
    ExecutionOutcome.LAUNCH_FAILED: RetryEligibility.ALWAYS,
    ExecutionOutcome.OUTCOME_FAILED: RetryEligibility.BY_POLICY,
    ExecutionOutcome.TIMED_OUT: RetryEligibility.BY_POLICY,
    ExecutionOutcome.CANCELLED: RetryEligibility.NEVER,
    ExecutionOutcome.SKIPPED: RetryEligibility.NEVER,
    ExecutionOutcome.BLOCKED: RetryEligibility.NEVER,
    ExecutionOutcome.CONDITION_ERROR: RetryEligibility.ALWAYS,
    ExecutionOutcome.INFRASTRUCTURE_FAILED: RetryEligibility.ALWAYS,
    ExecutionOutcome.UNKNOWN: RetryEligibility.NEVER,
}


_LEGAL_TRANSITIONS: Final[dict[ExecutionState, frozenset[ExecutionState]]] = {
    ExecutionState.PENDING: frozenset({ExecutionState.EVALUATING, ExecutionState.FINISHED}),
    # Evaluation may finish directly: a skipped or blocked execution never runs.
    ExecutionState.EVALUATING: frozenset({ExecutionState.RUNNING, ExecutionState.FINISHED}),
    ExecutionState.RUNNING: frozenset({ExecutionState.CANCELLING, ExecutionState.FINISHED}),
    ExecutionState.CANCELLING: frozenset({ExecutionState.FINISHED}),
    ExecutionState.FINISHED: frozenset(),
}


def is_legal_transition(current: ExecutionState, proposed: ExecutionState) -> bool:
    """Whether an execution may move between two states.

    Args:
        current: The state now.
        proposed: The state being requested.

    Returns:
        ``True`` when the transition is permitted.
    """
    return proposed in _LEGAL_TRANSITIONS[current]


def assert_legal_transition(current: ExecutionState, proposed: ExecutionState) -> None:
    """Raise unless an execution may move between two states.

    Args:
        current: The state now.
        proposed: The state being requested.

    Raises:
        DomainRuleViolationError: If the transition is not permitted.
    """
    from taskcontrol.common.errors import DomainRuleViolationError

    if not is_legal_transition(current, proposed):
        raise DomainRuleViolationError(
            f"Cannot move an execution from {current} to {proposed}.",
            details={
                "current_state": str(current),
                "proposed_state": str(proposed),
                "legal_states": sorted(str(s) for s in _LEGAL_TRANSITIONS[current]),
            },
        )


class ReasonCode:
    """Why an execution reached its outcome.

    Outcome answers *what*; reason code answers *why*. The vocabulary is open and
    namespaced by outcome — ``skipped.calendar_closed``, ``blocked.overlap_lock_held`` —
    so adding a code is not a breaking change and clients must tolerate unknown codes.

    A reason code is never encoded into the outcome. They are stored side by side.

    Attributes:
        value: The namespaced code.
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        """Validate and hold a reason code.

        Args:
            value: A ``<outcome>.<reason>`` code.

        Raises:
            ValidationError: If the code is malformed or its namespace is not an outcome
                that carries reason codes.
        """
        if not isinstance(value, str) or not value:
            raise ValidationError("ReasonCode must be a non-empty string.")

        namespace, separator, detail = value.partition(".")
        if not separator or not detail:
            raise ValidationError(
                "ReasonCode must be namespaced as '<outcome>.<reason>'.",
                details={"reason_code": value},
            )
        if namespace not in {outcome.value for outcome in _OUTCOMES_PERMITTING_REASON}:
            raise ValidationError(
                "ReasonCode namespace must be an outcome that carries reason codes.",
                details={
                    "reason_code": value,
                    "permitted_namespaces": sorted(
                        outcome.value for outcome in _OUTCOMES_PERMITTING_REASON
                    ),
                },
            )
        self._value = value

    @property
    def value(self) -> str:
        """The namespaced code."""
        return self._value

    @property
    def outcome(self) -> ExecutionOutcome:
        """The outcome this code belongs to, derived from its namespace."""
        return ExecutionOutcome(self._value.partition(".")[0])

    def matches(self, outcome: ExecutionOutcome) -> bool:
        """Whether this code belongs to a given outcome.

        Args:
            outcome: The outcome to check against.

        Returns:
            ``True`` when the namespaces agree.
        """
        return self.outcome is outcome

    @classmethod
    def from_primitive(cls, value: str) -> Self:
        """Build from a stored value."""
        return cls(value)

    def to_primitive(self) -> str:
        """Return the namespaced code."""
        return self._value

    def __str__(self) -> str:
        """Return the namespaced code."""
        return self._value

    def __repr__(self) -> str:
        """Return an unambiguous representation."""
        return f"ReasonCode({self._value!r})"

    def __eq__(self, other: object) -> bool:
        """Compare by code value."""
        if not isinstance(other, ReasonCode):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        """Hash by code value."""
        return hash(self._value)


class ReasonCodes:
    """The reason codes TaskControl itself produces.

    Registered rather than free-form so that the codes the product emits are discoverable,
    documented, and stable. The type still accepts unregistered codes, because a plugin or
    a later wave must be able to add one without editing this class.
    """

    SKIPPED_CALENDAR_CLOSED: Final = ReasonCode("skipped.calendar_closed")
    SKIPPED_SWITCH_DISABLED: Final = ReasonCode("skipped.switch_disabled")
    SKIPPED_ENVIRONMENT_NOT_ALLOWED: Final = ReasonCode("skipped.environment_not_allowed")
    SKIPPED_WINDOW_CLOSED: Final = ReasonCode("skipped.window_closed")
    SKIPPED_TASK_SUSPENDED: Final = ReasonCode("skipped.task_suspended")

    BLOCKED_OVERLAP_LOCK_HELD: Final = ReasonCode("blocked.overlap_lock_held")
    BLOCKED_DEPENDENCY_NOT_SATISFIED: Final = ReasonCode("blocked.dependency_not_satisfied")
    BLOCKED_MANUAL_HOLD: Final = ReasonCode("blocked.manual_hold")
    BLOCKED_APPROVAL_PENDING: Final = ReasonCode("blocked.approval_pending")
    BLOCKED_CONCURRENCY_LIMIT: Final = ReasonCode("blocked.concurrency_limit")

    CONDITION_ERROR_EVALUATOR_FAILED: Final = ReasonCode("condition_error.evaluator_failed")
    CONDITION_ERROR_CALENDAR_UNAVAILABLE: Final = ReasonCode("condition_error.calendar_unavailable")

    INFRASTRUCTURE_EXECUTOR_UNAVAILABLE: Final = ReasonCode(
        "infrastructure_failed.executor_unavailable"
    )
    INFRASTRUCTURE_TARGET_UNREACHABLE: Final = ReasonCode(
        "infrastructure_failed.target_unreachable"
    )
    INFRASTRUCTURE_STORAGE_FAILED: Final = ReasonCode("infrastructure_failed.storage_failed")

    # ADR 0020: at the operating-system level these three are the same event — a killed
    # process. Only the runtime knows which one it asked for.
    TIMED_OUT_RUN_TIMEOUT_EXCEEDED: Final = ReasonCode("timed_out.run_timeout_exceeded")
    CANCELLED_REQUESTED_BY_USER: Final = ReasonCode("cancelled.requested_by_user")
    CANCELLED_SUPERSEDED: Final = ReasonCode("cancelled.superseded")
    FAILED_TERMINATED_EXTERNALLY: Final = ReasonCode("failed.terminated_externally")

    @classmethod
    def registered(cls) -> frozenset[ReasonCode]:
        """Return every reason code TaskControl itself emits.

        Returns:
            The registered codes.
        """
        return frozenset(value for value in vars(cls).values() if isinstance(value, ReasonCode))

    @classmethod
    def for_outcome(cls, outcome: ExecutionOutcome) -> frozenset[ReasonCode]:
        """Return the registered codes belonging to one outcome.

        Args:
            outcome: The outcome to filter by.

        Returns:
            Matching registered codes, empty when the outcome carries none.
        """
        return frozenset(code for code in cls.registered() if code.matches(outcome))
