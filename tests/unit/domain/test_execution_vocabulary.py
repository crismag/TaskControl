"""The execution vocabulary, tested against ADR 0016 member by member.

The distinction between skip, block, process failure, outcome failure, timeout,
cancellation, infrastructure failure, and unproven state is the product's central claim.
If these tests weaken, the claim weakens.
"""

from __future__ import annotations

from enum import StrEnum

import pytest

from taskcontrol.common.errors import DomainRuleViolationError, ValidationError
from taskcontrol.domain.execution import (
    ExecutionOutcome,
    ExecutionState,
    ReasonCode,
    ReasonCodes,
    RetryEligibility,
    assert_legal_transition,
    is_legal_transition,
)

ALL_STATES = list(ExecutionState)
ALL_OUTCOMES = list(ExecutionOutcome)


class TestAdr0016Membership:
    """The enums contain exactly what ADR 0016 says, no more and no less."""

    def test_execution_states_match_the_adr(self) -> None:
        assert {state.value for state in ExecutionState} == {
            "pending",
            "evaluating",
            "running",
            "cancelling",
            "finished",
        }

    def test_execution_outcomes_match_the_adr(self) -> None:
        assert {outcome.value for outcome in ExecutionOutcome} == {
            "succeeded",
            "failed",
            "launch_failed",
            "outcome_failed",
            "timed_out",
            "cancelled",
            "skipped",
            "blocked",
            "condition_error",
            "infrastructure_failed",
            "unknown",
        }

    def test_removed_members_stay_removed(self) -> None:
        """`suppressed` is a notification concern; `lost` became UNKNOWN."""
        values = {outcome.value for outcome in ExecutionOutcome}
        assert "suppressed" not in values
        assert "lost" not in values

    @pytest.mark.parametrize("member", [*ALL_STATES, *ALL_OUTCOMES])
    def test_every_value_is_lower_snake_case(self, member: StrEnum) -> None:
        """One wire format, so API, CLI, UI, logs, and metrics agree."""
        assert member.value == member.value.lower()
        assert " " not in member.value
        assert "-" not in member.value


class TestOutcomeSemantics:
    def test_only_succeeded_is_a_success(self) -> None:
        successes = [outcome for outcome in ALL_OUTCOMES if outcome.is_success]
        assert successes == [ExecutionOutcome.SUCCEEDED]

    def test_a_skip_is_not_a_success(self) -> None:
        assert not ExecutionOutcome.SKIPPED.is_success

    def test_outcome_failed_is_not_a_success(self) -> None:
        """A zero exit with a failed required expectation is not success."""
        assert not ExecutionOutcome.OUTCOME_FAILED.is_success

    @pytest.mark.parametrize(
        "outcome",
        [
            ExecutionOutcome.SUCCEEDED,
            ExecutionOutcome.FAILED,
            ExecutionOutcome.OUTCOME_FAILED,
            ExecutionOutcome.TIMED_OUT,
            ExecutionOutcome.CANCELLED,
        ],
    )
    def test_outcomes_that_ran_a_process(self, outcome: ExecutionOutcome) -> None:
        assert outcome.ran

    @pytest.mark.parametrize(
        "outcome",
        [
            ExecutionOutcome.SKIPPED,
            ExecutionOutcome.BLOCKED,
            ExecutionOutcome.LAUNCH_FAILED,
            ExecutionOutcome.CONDITION_ERROR,
            ExecutionOutcome.INFRASTRUCTURE_FAILED,
            ExecutionOutcome.UNKNOWN,
        ],
    )
    def test_outcomes_where_no_process_ran(self, outcome: ExecutionOutcome) -> None:
        assert not outcome.ran

    def test_skipped_and_blocked_are_distinct(self) -> None:
        """Should-not-run and should-run-but-cannot-start-yet are different states."""
        assert ExecutionOutcome.SKIPPED not in {ExecutionOutcome.BLOCKED}

    @pytest.mark.parametrize(
        "outcome",
        [
            ExecutionOutcome.SKIPPED,
            ExecutionOutcome.BLOCKED,
            ExecutionOutcome.CONDITION_ERROR,
            ExecutionOutcome.INFRASTRUCTURE_FAILED,
        ],
    )
    def test_outcomes_that_require_a_reason_code(self, outcome: ExecutionOutcome) -> None:
        assert outcome.requires_reason_code

    def test_succeeded_needs_no_reason_code(self) -> None:
        assert not ExecutionOutcome.SUCCEEDED.requires_reason_code


class TestRetryEligibility:
    """The eligibility table from ADR 0016, asserted exhaustively."""

    EXPECTED = {
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

    @pytest.mark.parametrize("outcome", ALL_OUTCOMES)
    def test_eligibility_matches_the_adr(self, outcome: ExecutionOutcome) -> None:
        assert outcome.retry_eligibility is self.EXPECTED[outcome]

    def test_every_outcome_has_an_eligibility(self) -> None:
        assert set(self.EXPECTED) == set(ALL_OUTCOMES)

    def test_a_skip_is_never_retried(self) -> None:
        """Retrying a skip would run work that policy just declined to run."""
        assert ExecutionOutcome.SKIPPED.retry_eligibility is RetryEligibility.NEVER

    def test_unknown_is_never_blindly_retried(self) -> None:
        """An unproven execution may already have applied its effects."""
        assert ExecutionOutcome.UNKNOWN.retry_eligibility is RetryEligibility.NEVER


class TestStateTransitions:
    @pytest.mark.parametrize(
        ("current", "proposed"),
        [
            (ExecutionState.PENDING, ExecutionState.EVALUATING),
            (ExecutionState.PENDING, ExecutionState.FINISHED),
            (ExecutionState.EVALUATING, ExecutionState.RUNNING),
            (ExecutionState.EVALUATING, ExecutionState.FINISHED),
            (ExecutionState.RUNNING, ExecutionState.CANCELLING),
            (ExecutionState.RUNNING, ExecutionState.FINISHED),
            (ExecutionState.CANCELLING, ExecutionState.FINISHED),
        ],
    )
    def test_legal_transitions(self, current: ExecutionState, proposed: ExecutionState) -> None:
        assert is_legal_transition(current, proposed)

    @pytest.mark.parametrize(
        ("current", "proposed"),
        [
            (ExecutionState.PENDING, ExecutionState.RUNNING),
            (ExecutionState.PENDING, ExecutionState.CANCELLING),
            (ExecutionState.RUNNING, ExecutionState.PENDING),
            (ExecutionState.RUNNING, ExecutionState.EVALUATING),
            (ExecutionState.CANCELLING, ExecutionState.RUNNING),
            (ExecutionState.FINISHED, ExecutionState.RUNNING),
            (ExecutionState.FINISHED, ExecutionState.PENDING),
            (ExecutionState.FINISHED, ExecutionState.FINISHED),
        ],
    )
    def test_illegal_transitions(self, current: ExecutionState, proposed: ExecutionState) -> None:
        assert not is_legal_transition(current, proposed)

    def test_evaluating_may_finish_without_running(self) -> None:
        """A skipped or blocked execution is recorded, having never started a process."""
        assert is_legal_transition(ExecutionState.EVALUATING, ExecutionState.FINISHED)

    def test_finished_is_terminal(self) -> None:
        assert ExecutionState.FINISHED.is_terminal
        assert all(not is_legal_transition(ExecutionState.FINISHED, state) for state in ALL_STATES)

    def test_only_finished_requires_an_outcome(self) -> None:
        requiring = [state for state in ALL_STATES if state.requires_outcome]
        assert requiring == [ExecutionState.FINISHED]

    def test_assert_raises_a_domain_rule_violation(self) -> None:
        with pytest.raises(DomainRuleViolationError) as caught:
            assert_legal_transition(ExecutionState.FINISHED, ExecutionState.RUNNING)
        assert caught.value.details["current_state"] == "finished"
        assert caught.value.details["proposed_state"] == "running"

    def test_assert_permits_a_legal_transition(self) -> None:
        assert_legal_transition(ExecutionState.PENDING, ExecutionState.EVALUATING)


class TestReasonCode:
    def test_accepts_a_namespaced_code(self) -> None:
        assert ReasonCode("skipped.calendar_closed").outcome is ExecutionOutcome.SKIPPED

    @pytest.mark.parametrize(
        "value",
        ["", "calendar_closed", "skipped.", ".calendar_closed", "succeeded.everything_fine"],
    )
    def test_rejects_malformed_or_wrongly_namespaced_codes(self, value: str) -> None:
        with pytest.raises(ValidationError):
            ReasonCode(value)

    def test_rejects_a_non_string(self) -> None:
        with pytest.raises(ValidationError):
            ReasonCode(None)  # type: ignore[arg-type]

    def test_namespace_must_be_an_outcome_that_carries_reasons(self) -> None:
        """`succeeded` needs no reason, so a code namespaced under it is a mistake."""
        with pytest.raises(ValidationError) as caught:
            ReasonCode("succeeded.all_good")
        assert "permitted_namespaces" in caught.value.details

    def test_matches_its_outcome(self) -> None:
        code = ReasonCodes.BLOCKED_OVERLAP_LOCK_HELD
        assert code.matches(ExecutionOutcome.BLOCKED)
        assert not code.matches(ExecutionOutcome.SKIPPED)

    def test_accepts_an_unregistered_code(self) -> None:
        """The vocabulary is open: a plugin must be able to add a reason."""
        assert ReasonCode("skipped.custom_plugin_reason").outcome is ExecutionOutcome.SKIPPED

    def test_equality_and_hashing_are_by_value(self) -> None:
        assert ReasonCode("skipped.calendar_closed") == ReasonCode("skipped.calendar_closed")
        assert len({ReasonCode("blocked.manual_hold"), ReasonCode("blocked.manual_hold")}) == 1

    def test_round_trips(self) -> None:
        code = ReasonCodes.SKIPPED_CALENDAR_CLOSED
        assert ReasonCode.from_primitive(code.to_primitive()) == code


class TestReasonCodeRegistry:
    def test_registry_is_not_empty(self) -> None:
        assert ReasonCodes.registered()

    @pytest.mark.parametrize("code", sorted(ReasonCodes.registered(), key=str))
    def test_every_registered_code_is_valid(self, code: ReasonCode) -> None:
        assert ReasonCode(code.value) == code

    @pytest.mark.parametrize(
        "outcome",
        [
            ExecutionOutcome.SKIPPED,
            ExecutionOutcome.BLOCKED,
            ExecutionOutcome.CONDITION_ERROR,
            ExecutionOutcome.INFRASTRUCTURE_FAILED,
        ],
    )
    def test_every_reason_bearing_outcome_has_at_least_one_code(
        self, outcome: ExecutionOutcome
    ) -> None:
        """An outcome that requires a reason but offers none would be unusable."""
        assert ReasonCodes.for_outcome(outcome)

    def test_outcomes_without_reasons_have_no_registered_codes(self) -> None:
        assert ReasonCodes.for_outcome(ExecutionOutcome.SUCCEEDED) == frozenset()
