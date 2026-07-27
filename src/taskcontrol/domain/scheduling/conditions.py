"""Whether a task is *allowed* to run now.

A schedule says when to consider running. A run condition says whether to proceed. The
separation is the product's founding idea: a trigger that fires and does not run is a
normal outcome, recorded with a reason, not a silent no-op or a fake success.

Every condition returns a :class:`ConditionDecision` carrying allow/deny, a machine-readable
reason code, a human explanation, and the evidence behind it. A condition that returns a
bare boolean would make "why was this skipped?" unanswerable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any

from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.execution.vocabulary import (
    ExecutionOutcome,
    ReasonCode,
    ReasonCodes,
)
from taskcontrol.domain.scheduling.calendars import Calendar
from taskcontrol.domain.scheduling.schedules import Weekday


class ConditionVerdict(StrEnum):
    """The three possible answers to "may this run".

    Three, not two. "I could not tell" is different from "no", and conflating them is how
    a monitoring outage silently becomes a skipped nightly job.
    """

    ALLOW = "allow"
    "Proceed."

    DENY = "deny"
    "Do not proceed. Maps to SKIPPED or BLOCKED depending on the condition."

    ERROR = "error"
    "Eligibility could not be determined. Maps to CONDITION_ERROR."


@dataclass(frozen=True, slots=True)
class ConditionDecision:
    """One condition's answer, with everything needed to explain it later.

    Attributes:
        verdict: Allow, deny, or error.
        condition_name: Which condition decided.
        reason_code: The machine-readable reason, required unless allowing.
        explanation: A human-readable sentence.
        evidence: Structured detail behind the decision, safe to store and display.
    """

    verdict: ConditionVerdict
    condition_name: str
    reason_code: ReasonCode | None = None
    explanation: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the decision.

        Raises:
            ValidationError: If a non-allowing decision carries no reason code.
        """
        if self.verdict is not ConditionVerdict.ALLOW and self.reason_code is None:
            raise ValidationError(
                "A condition that denies or errors must supply a reason code. Without "
                "one, the resulting skip cannot be explained.",
                details={"condition": self.condition_name, "verdict": str(self.verdict)},
            )

    @property
    def allows(self) -> bool:
        """Whether this condition permits execution."""
        return self.verdict is ConditionVerdict.ALLOW

    def to_primitive(self) -> dict[str, Any]:
        """Return a stable representation."""
        return {
            "condition": self.condition_name,
            "verdict": str(self.verdict),
            "reason_code": self.reason_code.to_primitive() if self.reason_code else None,
            "explanation": self.explanation,
            "evidence": self.evidence,
        }


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    """The combined verdict of every condition evaluated, in order.

    Attributes:
        decisions: Every decision made, in evaluation order.
    """

    decisions: tuple[ConditionDecision, ...] = ()

    @property
    def allowed(self) -> bool:
        """Whether every condition allowed execution."""
        return all(decision.allows for decision in self.decisions)

    @property
    def blocking_decision(self) -> ConditionDecision | None:
        """The first decision that prevented execution, if any."""
        return next((decision for decision in self.decisions if not decision.allows), None)

    def outcome(self) -> ExecutionOutcome | None:
        """Map the result to the execution outcome it produces.

        Returns:
            ``None`` when execution may proceed, otherwise the outcome to record. The
            mapping honours ADR 0016: an error in the guard itself is ``CONDITION_ERROR``,
            while a deliberate refusal is ``SKIPPED`` or ``BLOCKED`` depending on which
            reason code the condition supplied.
        """
        decision = self.blocking_decision
        if decision is None:
            return None
        if decision.verdict is ConditionVerdict.ERROR:
            return ExecutionOutcome.CONDITION_ERROR
        return decision.reason_code.outcome if decision.reason_code else ExecutionOutcome.SKIPPED

    def explain(self) -> str:
        """Explain the overall result.

        Returns:
            A sentence describing why execution proceeded or did not.
        """
        decision = self.blocking_decision
        if decision is None:
            count = len(self.decisions)
            return f"All {count} run conditions allowed execution."
        return decision.explanation

    def to_primitive(self) -> dict[str, Any]:
        """Return a stable representation."""
        outcome = self.outcome()
        return {
            "allowed": self.allowed,
            "outcome": str(outcome) if outcome else None,
            "explanation": self.explain(),
            "decisions": [decision.to_primitive() for decision in self.decisions],
        }


@dataclass(frozen=True, slots=True)
class EnabledSwitch:
    """A named switch that turns a family of tasks off without editing schedules.

    Journey 7: an operator needs to stop a group of tasks during maintenance. Every skip
    it causes names the switch, so nobody has to guess why the estate went quiet.

    Attributes:
        name: The switch's name.
        enabled: Whether work may proceed.
        reason: Why it was turned off.
    """

    name: str
    enabled: bool = True
    reason: str = ""

    def evaluate(self) -> ConditionDecision:
        """Evaluate the switch.

        Returns:
            The decision, naming the switch and its resolved value.
        """
        if self.enabled:
            return ConditionDecision(
                verdict=ConditionVerdict.ALLOW,
                condition_name=f"switch:{self.name}",
                explanation=f"Switch {self.name!r} is enabled.",
                evidence={"switch": self.name, "enabled": True},
            )

        detail = f" ({self.reason})" if self.reason else ""
        return ConditionDecision(
            verdict=ConditionVerdict.DENY,
            condition_name=f"switch:{self.name}",
            reason_code=ReasonCodes.SKIPPED_SWITCH_DISABLED,
            explanation=f"Switch {self.name!r} is disabled{detail}.",
            evidence={"switch": self.name, "enabled": False, "reason": self.reason},
        )


@dataclass(frozen=True, slots=True)
class CalendarOpenCondition:
    """Requires the business calendar to be open on the execution date.

    Attributes:
        calendar: The calendar to consult.
    """

    calendar: Calendar

    def evaluate(self, day: date) -> ConditionDecision:
        """Evaluate the calendar for a date.

        Args:
            day: The date to evaluate, already in the intended local zone.

        Returns:
            The decision, carrying the calendar verdict as evidence so the skip can be
            reproduced against the calendar version that was in force.
        """
        verdict = self.calendar.classify(day)
        name = f"calendar:{self.calendar.slug}"

        if verdict.is_open:
            return ConditionDecision(
                verdict=ConditionVerdict.ALLOW,
                condition_name=name,
                explanation=verdict.explain(),
                evidence=verdict.to_primitive(),
            )

        return ConditionDecision(
            verdict=ConditionVerdict.DENY,
            condition_name=name,
            reason_code=ReasonCodes.SKIPPED_CALENDAR_CLOSED,
            explanation=verdict.explain(),
            evidence=verdict.to_primitive(),
        )


@dataclass(frozen=True, slots=True)
class AllowedWeekdaysCondition:
    """Requires the execution date to fall on a permitted weekday.

    Simpler than a calendar and independent of one. Useful when a task should not run at
    weekends but no business calendar exists yet.

    Attributes:
        weekdays: The permitted days.
    """

    weekdays: frozenset[Weekday]

    def __post_init__(self) -> None:
        """Validate the condition.

        Raises:
            ValidationError: If no weekday is permitted, which would deny every day.
        """
        if not self.weekdays:
            raise ValidationError(
                "An allowed-weekdays condition must permit at least one day, or it would "
                "deny every execution.",
            )

    def evaluate(self, day: date) -> ConditionDecision:
        """Evaluate the weekday of a date.

        Args:
            day: The date to evaluate.

        Returns:
            The decision.
        """
        weekday = Weekday.from_date_object(day)
        permitted = sorted(item.value for item in self.weekdays)

        if weekday in self.weekdays:
            return ConditionDecision(
                verdict=ConditionVerdict.ALLOW,
                condition_name="allowed_weekdays",
                explanation=f"{day.isoformat()} is a {weekday.value}, which is permitted.",
                evidence={"weekday": weekday.value, "permitted": permitted},
            )

        return ConditionDecision(
            verdict=ConditionVerdict.DENY,
            condition_name="allowed_weekdays",
            reason_code=ReasonCodes.SKIPPED_WINDOW_CLOSED,
            explanation=(
                f"{day.isoformat()} is a {weekday.value}; this task runs only on "
                f"{', '.join(permitted)}."
            ),
            evidence={"weekday": weekday.value, "permitted": permitted},
        )


@dataclass(frozen=True, slots=True)
class AllowedEnvironmentsCondition:
    """Requires the running environment to be one the task permits.

    Stops a production-only task from running in staging because a profile was copied
    without thinking.

    Attributes:
        environments: The permitted environment names.
    """

    environments: frozenset[str]

    def __post_init__(self) -> None:
        """Validate the condition.

        Raises:
            ValidationError: If no environment is permitted.
        """
        if not self.environments:
            raise ValidationError(
                "An allowed-environments condition must permit at least one environment.",
            )

    def evaluate(self, environment: str) -> ConditionDecision:
        """Evaluate the current environment.

        Args:
            environment: The environment this process is running in.

        Returns:
            The decision.
        """
        permitted = sorted(self.environments)
        if environment in self.environments:
            return ConditionDecision(
                verdict=ConditionVerdict.ALLOW,
                condition_name="allowed_environments",
                explanation=f"Environment {environment!r} is permitted.",
                evidence={"environment": environment, "permitted": permitted},
            )

        return ConditionDecision(
            verdict=ConditionVerdict.DENY,
            condition_name="allowed_environments",
            reason_code=ReasonCodes.SKIPPED_ENVIRONMENT_NOT_ALLOWED,
            explanation=(
                f"Environment {environment!r} is not permitted; this task runs only in "
                f"{', '.join(permitted)}."
            ),
            evidence={"environment": environment, "permitted": permitted},
        )


def combine(decisions: tuple[ConditionDecision, ...]) -> EligibilityResult:
    """Combine condition decisions into one eligibility result.

    Decisions are kept in evaluation order and all of them are retained, including those
    made after the first denial if the caller evaluated them. Recording only the first
    failure would lose evidence an operator may need.

    Args:
        decisions: The decisions, in the order they were evaluated.

    Returns:
        The combined result.
    """
    return EligibilityResult(decisions=decisions)
