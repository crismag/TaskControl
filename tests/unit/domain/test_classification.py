"""Classification and retry decisions.

The rule under test throughout: **exiting zero is not sufficient for success.** If these
tests pass but the product still reports a green run for a task that produced no report,
the tests are wrong.
"""

from __future__ import annotations

import pytest

from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.common import Duration
from taskcontrol.domain.execution import (
    BackoffStrategy,
    ExecutionOutcome,
    ProcessResult,
    RetryPolicy,
    TerminationMode,
    TimeoutPolicy,
)
from taskcontrol.domain.policies import (
    ExpectationEvidence,
    classify_process_result,
    decide_retry,
)

ONE_SECOND = Duration(1)


class TestProcessResultValidation:
    def test_an_exited_process_needs_an_exit_code(self) -> None:
        with pytest.raises(ValidationError):
            ProcessResult(termination=TerminationMode.EXITED, duration=ONE_SECOND)

    def test_only_an_exited_process_may_report_an_exit_code(self) -> None:
        with pytest.raises(ValidationError):
            ProcessResult(termination=TerminationMode.ABANDONED, duration=ONE_SECOND, exit_code=0)

    def test_a_signalled_process_needs_a_signal_number(self) -> None:
        with pytest.raises(ValidationError):
            ProcessResult(termination=TerminationMode.SIGNALLED, duration=ONE_SECOND)

    def test_only_a_signalled_process_may_report_a_signal(self) -> None:
        with pytest.raises(ValidationError):
            ProcessResult.exited(0, ONE_SECOND, signal_number=9)

    def test_a_process_that_did_not_start_must_explain_why(self) -> None:
        with pytest.raises(ValidationError):
            ProcessResult(termination=TerminationMode.NOT_STARTED, duration=ONE_SECOND)

    def test_rejects_an_out_of_range_exit_code(self) -> None:
        with pytest.raises(ValidationError):
            ProcessResult.exited(300, ONE_SECOND)

    def test_rejects_negative_output_sizes(self) -> None:
        with pytest.raises(ValidationError):
            ProcessResult.exited(0, ONE_SECOND, stdout_bytes=-1)

    def test_exited_cleanly_reflects_status_zero(self) -> None:
        assert ProcessResult.exited(0, ONE_SECOND).exited_cleanly
        assert not ProcessResult.exited(1, ONE_SECOND).exited_cleanly

    def test_not_started_means_no_process_ran(self) -> None:
        assert not ProcessResult.not_started("binary missing").started


class TestClassification:
    def test_clean_exit_with_no_expectations_succeeds(self) -> None:
        result = classify_process_result(ProcessResult.exited(0, ONE_SECOND))
        assert result.outcome is ExecutionOutcome.SUCCEEDED

    def test_clean_exit_with_passing_expectations_succeeds(self) -> None:
        result = classify_process_result(
            ProcessResult.exited(0, ONE_SECOND),
            expectations=ExpectationEvidence(required_total=3, required_failed=0),
        )
        assert result.outcome is ExecutionOutcome.SUCCEEDED

    def test_clean_exit_with_a_failed_expectation_is_outcome_failed(self) -> None:
        """The product's central claim: a zero exit does not prove the work happened."""
        result = classify_process_result(
            ProcessResult.exited(0, ONE_SECOND),
            expectations=ExpectationEvidence(required_total=2, required_failed=1),
        )
        assert result.outcome is ExecutionOutcome.OUTCOME_FAILED
        assert "1 of 2" in result.explanation

    def test_clean_exit_with_an_errored_evaluator_is_outcome_failed(self) -> None:
        """An unknown verdict is never silently treated as a pass."""
        result = classify_process_result(
            ProcessResult.exited(0, ONE_SECOND),
            expectations=ExpectationEvidence(required_total=1, evaluation_errored=True),
        )
        assert result.outcome is ExecutionOutcome.OUTCOME_FAILED

    def test_non_zero_exit_fails(self) -> None:
        result = classify_process_result(ProcessResult.exited(2, ONE_SECOND))
        assert result.outcome is ExecutionOutcome.FAILED
        assert "status 2" in result.explanation

    def test_custom_expected_exit_codes_are_honoured(self) -> None:
        """Some tools report 'nothing to do' with a non-zero status."""
        result = classify_process_result(
            ProcessResult.exited(1, ONE_SECOND), expected_exit_codes=frozenset({0, 1})
        )
        assert result.outcome is ExecutionOutcome.SUCCEEDED

    def test_custom_expected_codes_can_exclude_zero(self) -> None:
        result = classify_process_result(
            ProcessResult.exited(0, ONE_SECOND), expected_exit_codes=frozenset({3})
        )
        assert result.outcome is ExecutionOutcome.FAILED

    def test_a_process_that_did_not_start_is_launch_failed(self) -> None:
        """Not a failure of the work — the work never began."""
        result = classify_process_result(
            ProcessResult.not_started("No such file or directory: /usr/bin/nope")
        )
        assert result.outcome is ExecutionOutcome.LAUNCH_FAILED
        assert "/usr/bin/nope" in result.explanation

    def test_an_abandoned_process_is_unknown(self) -> None:
        """Honest reporting of unproven state, per ADR 0008 and ADR 0016."""
        result = classify_process_result(ProcessResult.abandoned(Duration(60)))
        assert result.outcome is ExecutionOutcome.UNKNOWN
        assert "reconciliation" in result.explanation

    def test_a_timeout_is_reported_as_a_timeout(self) -> None:
        result = classify_process_result(
            ProcessResult(
                termination=TerminationMode.SIGNALLED,
                signal_number=9,
                duration=Duration(120),
                timed_out=True,
            )
        )
        assert result.outcome is ExecutionOutcome.TIMED_OUT

    def test_timeout_takes_precedence_over_the_signal_that_enforced_it(self) -> None:
        """Reporting SIGKILL instead of the timeout would hide the actual cause."""
        result = classify_process_result(
            ProcessResult(
                termination=TerminationMode.SIGNALLED,
                signal_number=9,
                duration=Duration(120),
                timed_out=True,
            )
        )
        assert result.outcome is not ExecutionOutcome.FAILED

    def test_an_unexpected_signal_is_a_failure(self) -> None:
        result = classify_process_result(
            ProcessResult(
                termination=TerminationMode.SIGNALLED, signal_number=11, duration=ONE_SECOND
            )
        )
        assert result.outcome is ExecutionOutcome.FAILED
        assert "signal 11" in result.explanation

    def test_expectations_are_not_consulted_when_the_process_failed(self) -> None:
        """A failing process is FAILED; its expectations do not change the diagnosis."""
        result = classify_process_result(
            ProcessResult.exited(1, ONE_SECOND),
            expectations=ExpectationEvidence(required_total=1, required_failed=1),
        )
        assert result.outcome is ExecutionOutcome.FAILED

    def test_classification_is_pure(self) -> None:
        """Same inputs, same answer — which is what makes a record explainable later."""
        outcome = ProcessResult.exited(0, ONE_SECOND)
        evidence = ExpectationEvidence(required_total=1, required_failed=1)
        first = classify_process_result(outcome, expectations=evidence)
        second = classify_process_result(outcome, expectations=evidence)
        assert first == second

    def test_every_classification_carries_an_explanation(self) -> None:
        for result in (
            ProcessResult.exited(0, ONE_SECOND),
            ProcessResult.exited(7, ONE_SECOND),
            ProcessResult.not_started("missing"),
            ProcessResult.abandoned(ONE_SECOND),
        ):
            assert classify_process_result(result).explanation


class TestExpectationEvidence:
    def test_no_expectations_means_all_passed(self) -> None:
        assert ExpectationEvidence().all_required_passed

    def test_an_errored_evaluator_is_not_a_pass(self) -> None:
        assert not ExpectationEvidence(evaluation_errored=True).all_required_passed


class TestRetryPolicyValidation:
    def test_defaults_to_a_single_attempt(self) -> None:
        assert not RetryPolicy().retries_enabled

    def test_rejects_fewer_than_one_attempt(self) -> None:
        with pytest.raises(ValidationError):
            RetryPolicy(max_attempts=0)

    def test_rejects_an_absurd_attempt_count(self) -> None:
        with pytest.raises(ValidationError):
            RetryPolicy(max_attempts=10_000)

    def test_rejects_a_max_delay_shorter_than_the_base(self) -> None:
        with pytest.raises(ValidationError):
            RetryPolicy(max_attempts=3, base_delay=Duration(60), max_delay=Duration(30))

    def test_first_attempt_is_never_delayed(self) -> None:
        assert RetryPolicy(max_attempts=3).delay_before(1) == Duration(0)

    def test_rejects_a_non_positive_attempt_number(self) -> None:
        with pytest.raises(ValidationError):
            RetryPolicy().delay_before(0)

    @pytest.mark.parametrize(
        ("strategy", "expected"),
        [
            (BackoffStrategy.FIXED, [10, 10, 10]),
            (BackoffStrategy.LINEAR, [10, 20, 30]),
            (BackoffStrategy.EXPONENTIAL, [10, 20, 40]),
        ],
    )
    def test_backoff_growth(self, strategy: BackoffStrategy, expected: list[int]) -> None:
        policy = RetryPolicy(
            max_attempts=5, backoff=strategy, base_delay=Duration(10), max_delay=Duration(3600)
        )
        actual = [policy.delay_before(attempt).seconds for attempt in (2, 3, 4)]
        assert actual == expected

    def test_backoff_is_capped(self) -> None:
        policy = RetryPolicy(
            max_attempts=10,
            backoff=BackoffStrategy.EXPONENTIAL,
            base_delay=Duration(60),
            max_delay=Duration(300),
        )
        assert policy.delay_before(10) == Duration(300)


class TestRetryDecisions:
    RETRYING = RetryPolicy(max_attempts=3, base_delay=Duration(10), max_delay=Duration(100))

    def test_a_technical_failure_is_retried(self) -> None:
        decision = decide_retry(ExecutionOutcome.FAILED, policy=self.RETRYING, attempts_made=1)
        assert decision.should_retry
        assert decision.next_attempt_number == 2

    def test_a_skip_is_never_retried(self) -> None:
        decision = decide_retry(ExecutionOutcome.SKIPPED, policy=self.RETRYING, attempts_made=1)
        assert not decision.should_retry
        assert "never retried" in decision.reason

    @pytest.mark.parametrize(
        "outcome",
        [
            ExecutionOutcome.SUCCEEDED,
            ExecutionOutcome.CANCELLED,
            ExecutionOutcome.SKIPPED,
            ExecutionOutcome.BLOCKED,
            ExecutionOutcome.UNKNOWN,
        ],
    )
    def test_never_retryable_outcomes_ignore_a_permissive_policy(
        self, outcome: ExecutionOutcome
    ) -> None:
        assert not decide_retry(outcome, policy=self.RETRYING, attempts_made=1).should_retry

    def test_retries_stop_when_exhausted(self) -> None:
        decision = decide_retry(ExecutionOutcome.FAILED, policy=self.RETRYING, attempts_made=3)
        assert not decision.should_retry
        assert "exhausted" in decision.reason

    def test_a_single_attempt_policy_never_retries(self) -> None:
        decision = decide_retry(ExecutionOutcome.FAILED, policy=RetryPolicy.none(), attempts_made=1)
        assert not decision.should_retry

    def test_outcome_failure_requires_opting_in(self) -> None:
        """Re-running work that already produced side effects must be a deliberate choice."""
        decision = decide_retry(
            ExecutionOutcome.OUTCOME_FAILED, policy=self.RETRYING, attempts_made=1
        )
        assert not decision.should_retry
        assert "opts in" in decision.reason

    def test_outcome_failure_is_retried_when_opted_in(self) -> None:
        policy = RetryPolicy(max_attempts=3, retry_outcome_failures=True)
        decision = decide_retry(ExecutionOutcome.OUTCOME_FAILED, policy=policy, attempts_made=1)
        assert decision.should_retry

    def test_timeout_requires_opting_in(self) -> None:
        assert not decide_retry(
            ExecutionOutcome.TIMED_OUT, policy=self.RETRYING, attempts_made=1
        ).should_retry

    def test_timeout_is_retried_when_opted_in(self) -> None:
        policy = RetryPolicy(max_attempts=3, retry_timeouts=True)
        assert decide_retry(ExecutionOutcome.TIMED_OUT, policy=policy, attempts_made=1).should_retry

    def test_opting_into_one_policy_outcome_does_not_opt_into_the_other(self) -> None:
        policy = RetryPolicy(max_attempts=3, retry_timeouts=True)
        assert not decide_retry(
            ExecutionOutcome.OUTCOME_FAILED, policy=policy, attempts_made=1
        ).should_retry

    def test_every_decision_carries_a_reason(self) -> None:
        for outcome in ExecutionOutcome:
            decision = decide_retry(outcome, policy=self.RETRYING, attempts_made=1)
            assert decision.reason, f"{outcome} produced no reason"


class TestTimeoutPolicy:
    def test_defaults_to_unlimited_runtime(self) -> None:
        assert not TimeoutPolicy(run_timeout=Duration(0), termination_grace=Duration(0)).is_enforced

    def test_a_configured_timeout_is_enforced(self) -> None:
        assert TimeoutPolicy(run_timeout=Duration(600)).is_enforced

    def test_a_grace_period_without_a_timeout_is_rejected(self) -> None:
        """Nothing would ever trigger the grace period, so the configuration is a mistake."""
        with pytest.raises(ValidationError):
            TimeoutPolicy(run_timeout=Duration(0), termination_grace=Duration(30))

    def test_unlimited_is_explicit(self) -> None:
        policy = TimeoutPolicy.unlimited()
        assert not policy.is_enforced
        assert policy.termination_grace.is_zero
