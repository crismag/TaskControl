"""Process results and the execution-control policies that act on them.

A :class:`ProcessResult` is the raw truth of what an operating-system process did. It is
deliberately *not* an outcome: turning a result into an :class:`ExecutionOutcome` requires
expectation evidence and is the job of the classification policy.

Keeping them apart is what lets a process exit 0 and the execution still be
``OUTCOME_FAILED``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Self

from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.common.values import Duration

MAX_RETRY_ATTEMPTS = 100
MAX_EXIT_CODE = 255


class TerminationCause(StrEnum):
    """Why a process was terminated, recorded when termination is *requested*.

    At the operating-system level a timeout, a cancellation, and an external kill are the
    same event: a signal arrives and the process dies. Only the runtime knows which one it
    asked for, so the cause is recorded at the moment of the request rather than inferred
    afterwards from the signal number — inferring would be a guess, and ADR 0008 forbids
    guessing (ADR 0020).
    """

    NOT_TERMINATED = "not_terminated"
    "The process ended on its own."

    RUN_TIMEOUT = "run_timeout"
    "The runtime enforced the configured timeout."

    CANCELLATION_REQUESTED = "cancellation_requested"
    "An authorised cancellation asked the process to stop."

    SUPERSEDED = "superseded"
    "A replace-overlap policy cancelled this run in favour of a newer one."

    EXTERNAL = "external"
    "A signal arrived that TaskControl did not send: an operator, a supervisor, the OOM killer."


class TerminationMode(StrEnum):
    """How a process ended, from the runtime's point of view."""

    EXITED = "exited"
    "The process ran to completion and returned an exit code."

    SIGNALLED = "signalled"
    "The process was terminated by a signal."

    NOT_STARTED = "not_started"
    "The process could not be launched at all."

    ABANDONED = "abandoned"
    "The runtime lost track of the process; its fate is unproven."


@dataclass(frozen=True, slots=True)
class ProcessResult:
    """What one operating-system process actually did.

    Attributes:
        termination: How the process ended.
        exit_code: The exit status, when the process exited normally.
        signal_number: The terminating signal, when signalled.
        duration: Wall-clock time the process ran.
        termination_cause: Why the process was terminated, when it was.
        stdout_bytes: Size of captured standard output.
        stderr_bytes: Size of captured standard error.
        output_truncated: Whether captured output hit the configured size limit.
        launch_error: Why the process could not start, when it did not.
    """

    termination: TerminationMode
    duration: Duration
    exit_code: int | None = None
    signal_number: int | None = None
    termination_cause: TerminationCause = TerminationCause.NOT_TERMINATED
    stdout_bytes: int = 0
    stderr_bytes: int = 0
    output_truncated: bool = False
    launch_error: str | None = None

    def __post_init__(self) -> None:
        """Validate internal consistency.

        Raises:
            ValidationError: If the fields describe an impossible process result.
        """
        if self.termination is TerminationMode.EXITED:
            if self.exit_code is None:
                raise ValidationError("An exited process must report an exit code.")
            if not 0 <= self.exit_code <= MAX_EXIT_CODE:
                raise ValidationError(
                    "Exit code is outside the representable range.",
                    details={"exit_code": self.exit_code},
                )
        elif self.exit_code is not None:
            raise ValidationError(
                "Only an exited process may report an exit code.",
                details={"termination": str(self.termination)},
            )

        if self.termination is TerminationMode.SIGNALLED and self.signal_number is None:
            raise ValidationError("A signalled process must report a signal number.")
        if self.termination is not TerminationMode.SIGNALLED and self.signal_number is not None:
            raise ValidationError(
                "Only a signalled process may report a signal number.",
                details={"termination": str(self.termination)},
            )

        if self.termination is TerminationMode.NOT_STARTED and not self.launch_error:
            raise ValidationError("A process that did not start must explain why.")

        for name, size in (
            ("stdout_bytes", self.stdout_bytes),
            ("stderr_bytes", self.stderr_bytes),
        ):
            if size < 0:
                raise ValidationError(
                    "Captured output size cannot be negative.", details={"field": name}
                )

    @classmethod
    def exited(cls, exit_code: int, duration: Duration, **extra: Any) -> Self:
        """Build the result of a process that ran to completion."""
        return cls(
            termination=TerminationMode.EXITED,
            exit_code=exit_code,
            duration=duration,
            **extra,
        )

    @classmethod
    def not_started(cls, reason: str, duration: Duration | None = None) -> Self:
        """Build the result of a process that could not be launched."""
        return cls(
            termination=TerminationMode.NOT_STARTED,
            duration=duration or Duration(0),
            launch_error=reason,
        )

    @classmethod
    def terminated(
        cls, cause: TerminationCause, *, signal_number: int, duration: Duration, **extra: Any
    ) -> Self:
        """Build the result of a process that was terminated by a signal.

        Args:
            cause: Why it was terminated. Supplied by whoever requested the termination.
            signal_number: The signal that ended it.
            duration: How long it ran.
            **extra: Further result fields, such as captured output sizes.

        Returns:
            The result.
        """
        return cls(
            termination=TerminationMode.SIGNALLED,
            signal_number=signal_number,
            duration=duration,
            termination_cause=cause,
            **extra,
        )

    @classmethod
    def abandoned(cls, duration: Duration) -> Self:
        """Build the result of a process whose fate is unproven.

        Used after a control-plane restart finds an execution that was in flight. Its
        honest classification is ``UNKNOWN``, never a guessed failure.
        """
        return cls(termination=TerminationMode.ABANDONED, duration=duration)

    @property
    def timed_out(self) -> bool:
        """Whether the runtime terminated this process for exceeding its timeout."""
        return self.termination_cause is TerminationCause.RUN_TIMEOUT

    @property
    def was_terminated(self) -> bool:
        """Whether something ended this process rather than letting it finish."""
        return self.termination_cause is not TerminationCause.NOT_TERMINATED

    @property
    def started(self) -> bool:
        """Whether a process was actually launched."""
        return self.termination is not TerminationMode.NOT_STARTED

    @property
    def exited_cleanly(self) -> bool:
        """Whether the process exited with status zero."""
        return self.termination is TerminationMode.EXITED and self.exit_code == 0


class BackoffStrategy(StrEnum):
    """How the delay between retry attempts grows."""

    FIXED = "fixed"
    "Every retry waits the same interval."

    LINEAR = "linear"
    "The interval grows by the base delay each attempt."

    EXPONENTIAL = "exponential"
    "The interval doubles each attempt, up to the configured maximum."


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """How many times, and how soon, a failed execution may be retried.

    Retrying is not automatic for every failure. ``retry_outcome_failures`` and
    ``retry_timeouts`` exist because both cases can leave partially applied side effects,
    so the task must opt in rather than inherit a dangerous default.

    Attributes:
        max_attempts: Total attempts including the first. ``1`` means no retry.
        backoff: How the delay grows between attempts.
        base_delay: Delay before the first retry.
        max_delay: Ceiling on any computed delay.
        retry_outcome_failures: Whether an ``OUTCOME_FAILED`` result may be retried.
        retry_timeouts: Whether a ``TIMED_OUT`` result may be retried.
    """

    max_attempts: int = 1
    backoff: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    base_delay: Duration = field(default_factory=lambda: Duration(30))
    max_delay: Duration = field(default_factory=lambda: Duration(3600))
    retry_outcome_failures: bool = False
    retry_timeouts: bool = False

    def __post_init__(self) -> None:
        """Validate the policy.

        Raises:
            ValidationError: If the policy is unusable or self-contradictory.
        """
        if isinstance(self.max_attempts, bool) or not isinstance(self.max_attempts, int):
            raise ValidationError("RetryPolicy max_attempts must be an integer.")
        if self.max_attempts < 1:
            raise ValidationError(
                "RetryPolicy max_attempts must be at least 1, which means no retry.",
                details={"max_attempts": self.max_attempts},
            )
        if self.max_attempts > MAX_RETRY_ATTEMPTS:
            raise ValidationError(
                "RetryPolicy max_attempts exceeds the supported maximum.",
                details={"max_attempts": self.max_attempts, "maximum": MAX_RETRY_ATTEMPTS},
            )
        if self.max_delay < self.base_delay:
            raise ValidationError(
                "RetryPolicy max_delay must not be shorter than base_delay.",
                details={
                    "base_delay_seconds": self.base_delay.seconds,
                    "max_delay_seconds": self.max_delay.seconds,
                },
            )

    @classmethod
    def none(cls) -> Self:
        """Return a policy that never retries."""
        return cls(max_attempts=1)

    @property
    def retries_enabled(self) -> bool:
        """Whether this policy permits more than one attempt."""
        return self.max_attempts > 1

    def delay_before(self, attempt_number: int) -> Duration:
        """Return the delay before a given attempt.

        Args:
            attempt_number: The 1-based attempt about to be made. Attempt 1 is the first
                run and is never delayed.

        Returns:
            The delay, capped at ``max_delay``.

        Raises:
            ValidationError: If the attempt number is not positive.
        """
        if attempt_number < 1:
            raise ValidationError(
                "Attempt numbers start at 1.", details={"attempt_number": attempt_number}
            )
        if attempt_number == 1:
            return Duration(0)

        retry_index = attempt_number - 2
        base = self.base_delay.seconds
        match self.backoff:
            case BackoffStrategy.FIXED:
                seconds = base
            case BackoffStrategy.LINEAR:
                seconds = base * (retry_index + 1)
            case BackoffStrategy.EXPONENTIAL:
                seconds = base * (2**retry_index)
        return Duration(min(seconds, self.max_delay.seconds))


@dataclass(frozen=True, slots=True)
class TimeoutPolicy:
    """How long an execution may run, and how it is stopped when it overruns.

    Termination is two-stage: a graceful signal, then a grace period, then a forceful
    kill. A task that ignores the first signal must still be stoppable, or a scheduled
    system accumulates stuck processes until it stops scheduling anything.

    Attributes:
        run_timeout: Maximum wall-clock runtime. Zero means no limit.
        termination_grace: Time allowed after the graceful signal before a forceful kill.
    """

    run_timeout: Duration = field(default_factory=lambda: Duration(0))
    termination_grace: Duration = field(default_factory=lambda: Duration(30))

    def __post_init__(self) -> None:
        """Validate the policy.

        Raises:
            ValidationError: If a grace period is configured without a timeout to enforce.
        """
        if self.run_timeout.is_zero and not self.termination_grace.is_zero:
            # Not fatal in isolation, but it signals a misunderstanding: with no timeout
            # nothing ever triggers the grace period.
            raise ValidationError(
                "A termination grace period requires a run timeout to enforce.",
                details={"termination_grace_seconds": self.termination_grace.seconds},
            )

    @classmethod
    def unlimited(cls) -> Self:
        """Return a policy that never times out.

        Appropriate only where overrun is genuinely acceptable. A scheduled task with no
        timeout can occupy its overlap lock forever.
        """
        return cls(run_timeout=Duration(0), termination_grace=Duration(0))

    @property
    def is_enforced(self) -> bool:
        """Whether a runtime limit applies."""
        return not self.run_timeout.is_zero


class OverlapPolicy(StrEnum):
    """What happens when a trigger arrives while the task is already running.

    ``ALLOW`` and ``FORBID`` are implemented first and reliably; ``QUEUE`` and ``REPLACE``
    require durable queueing and authorised cancellation respectively.
    """

    ALLOW = "allow"
    "Concurrent executions may overlap."

    FORBID = "forbid"
    "Decline to start while another execution is active. Produces ``BLOCKED``."

    QUEUE = "queue"
    "Wait until the prior execution finishes."

    REPLACE = "replace"
    "Cancel or supersede the prior execution, where explicitly authorised."
