"""Turning evidence into a decision.

Pure functions over stored inputs: same inputs, same answer, no I/O and no clock. That is
what makes an execution's classification reproducible and explainable months later, from
the record alone.

The classification rule that matters most: **a process exiting zero is not sufficient for
success.** Every required expectation must also pass. This is the product's central claim
expressed as code.
"""

from __future__ import annotations

from dataclasses import dataclass

from taskcontrol.domain.execution.results import ProcessResult, RetryPolicy, TerminationMode
from taskcontrol.domain.execution.vocabulary import (
    ExecutionOutcome,
    ReasonCode,
    RetryEligibility,
)


@dataclass(frozen=True, slots=True)
class ExpectationEvidence:
    """Summarised result of evaluating a revision's expected outcomes.

    Only counts are needed to classify. The individual results are stored separately, each
    with its own evidence, so a failure can be explained rather than merely counted.

    Attributes:
        required_total: Number of required expectations evaluated.
        required_failed: How many required expectations failed.
        evaluation_errored: Whether an evaluator itself failed to produce a verdict.
    """

    required_total: int = 0
    required_failed: int = 0
    evaluation_errored: bool = False

    @property
    def all_required_passed(self) -> bool:
        """Whether every required expectation passed.

        An evaluator that errored is not a pass: an unknown verdict must never be silently
        treated as satisfied.
        """
        return not self.evaluation_errored and self.required_failed == 0


@dataclass(frozen=True, slots=True)
class Classification:
    """The classified end state of an execution, with its explanation.

    Attributes:
        outcome: The terminal classification.
        reason_code: Why, for outcomes that require a reason.
        explanation: A human-readable sentence, safe to display.
    """

    outcome: ExecutionOutcome
    reason_code: ReasonCode | None = None
    explanation: str = ""


def classify_process_result(
    result: ProcessResult,
    *,
    expectations: ExpectationEvidence | None = None,
    expected_exit_codes: frozenset[int] | None = None,
) -> Classification:
    """Classify what a process did into a terminal outcome.

    The order of checks encodes the product's rules:

    1. A process that never started is a ``LAUNCH_FAILED``, not a failure of the work.
    2. A process whose fate is unproven is ``UNKNOWN``. It is never guessed either way.
    3. A timeout is a timeout, even though the process also died by signal.
    4. A technically failing exit is ``FAILED``.
    5. Only then, a technically successful process is checked against its expectations —
       and fails as ``OUTCOME_FAILED`` if any required one did not pass.

    Args:
        result: What the process did.
        expectations: Summarised expectation evidence. ``None`` means none were configured,
            in which case a technically successful process succeeds.
        expected_exit_codes: Exit codes to treat as success. Defaults to ``{0}``. Some
            tools legitimately report "nothing to do" as a non-zero code.

    Returns:
        The classification, with an explanation.
    """
    evidence = expectations or ExpectationEvidence()
    successful_codes = expected_exit_codes if expected_exit_codes is not None else frozenset({0})

    if result.termination is TerminationMode.NOT_STARTED:
        return Classification(
            ExecutionOutcome.LAUNCH_FAILED,
            explanation=result.launch_error or "The process could not be started.",
        )

    if result.termination is TerminationMode.ABANDONED:
        return Classification(
            ExecutionOutcome.UNKNOWN,
            explanation=(
                "The runtime lost track of the process, so its result cannot be proven. "
                "This execution requires reconciliation."
            ),
        )

    # Checked before the exit code: a timed-out process usually also reports a signal or a
    # non-zero status, and reporting that instead of the timeout would hide the cause.
    if result.timed_out:
        return Classification(
            ExecutionOutcome.TIMED_OUT,
            explanation=f"The process exceeded its timeout after {result.duration}.",
        )

    if result.termination is TerminationMode.SIGNALLED:
        return Classification(
            ExecutionOutcome.FAILED,
            explanation=f"The process was terminated by signal {result.signal_number}.",
        )

    if result.exit_code not in successful_codes:
        return Classification(
            ExecutionOutcome.FAILED,
            explanation=f"The process exited with status {result.exit_code}.",
        )

    if evidence.evaluation_errored:
        return Classification(
            ExecutionOutcome.OUTCOME_FAILED,
            explanation=(
                "The process succeeded, but an expected-outcome evaluator failed, "
                "so success could not be confirmed."
            ),
        )

    if evidence.required_failed > 0:
        return Classification(
            ExecutionOutcome.OUTCOME_FAILED,
            explanation=(
                f"The process exited with status {result.exit_code}, but "
                f"{evidence.required_failed} of {evidence.required_total} required "
                "expected outcomes did not pass."
            ),
        )

    return Classification(
        ExecutionOutcome.SUCCEEDED,
        explanation=(
            f"The process exited with status {result.exit_code} and every required "
            "expected outcome passed."
        )
        if evidence.required_total
        else f"The process exited with status {result.exit_code}.",
    )


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """Whether another attempt will be made, and why.

    Attributes:
        should_retry: Whether to attempt again.
        reason: A human-readable explanation, recorded against the execution.
        next_attempt_number: The attempt about to be made, when retrying.
    """

    should_retry: bool
    reason: str
    next_attempt_number: int | None = None


def decide_retry(
    outcome: ExecutionOutcome,
    *,
    policy: RetryPolicy,
    attempts_made: int,
) -> RetryDecision:
    """Decide whether a failed execution gets another attempt.

    Eligibility comes from the outcome (ADR 0016); permission comes from the policy. Both
    must agree. An outcome that is never retryable is not retried however the policy is
    configured — retrying a skip would run work that policy just declined.

    Args:
        outcome: How the last attempt ended.
        policy: The revision's retry policy.
        attempts_made: How many attempts have already completed.

    Returns:
        The decision, with a reason suitable for the execution record.
    """
    eligibility = outcome.retry_eligibility

    if eligibility is RetryEligibility.NEVER:
        return RetryDecision(False, f"{outcome} is never retried.")

    if not policy.retries_enabled:
        return RetryDecision(False, "The task's retry policy allows a single attempt.")

    if attempts_made >= policy.max_attempts:
        return RetryDecision(
            False,
            f"Retries exhausted after {attempts_made} of {policy.max_attempts} attempts.",
        )

    if eligibility is RetryEligibility.BY_POLICY:
        opted_in = (
            policy.retry_outcome_failures
            if outcome is ExecutionOutcome.OUTCOME_FAILED
            else policy.retry_timeouts
        )
        if not opted_in:
            return RetryDecision(
                False,
                (
                    f"{outcome} is retried only when the task opts in, because the work "
                    "may have partially applied its effects."
                ),
            )

    return RetryDecision(
        True,
        f"{outcome} is retryable; attempt {attempts_made + 1} of {policy.max_attempts}.",
        next_attempt_number=attempts_made + 1,
    )
