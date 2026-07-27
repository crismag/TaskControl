"""Schedules, calendars, and run conditions.

DST is tested against real transitions in three zones, because "06:00 local" quietly
becoming 05:00 or 07:00 twice a year is the defining failure of scheduled systems.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time

import pytest

from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.common import (
    CalendarId,
    Duration,
    RevisionNumber,
    Slug,
    TimeZoneName,
    UtcTimestamp,
)
from taskcontrol.domain.execution import ExecutionOutcome, ReasonCodes
from taskcontrol.domain.scheduling import (
    WORKING_WEEK,
    AllowedEnvironmentsCondition,
    AllowedWeekdaysCondition,
    Calendar,
    CalendarOpenCondition,
    ConditionDecision,
    ConditionVerdict,
    CronExpression,
    DayClassification,
    EnabledSwitch,
    IntervalSchedule,
    ManualSchedule,
    MisfirePolicy,
    Weekday,
    WeekdayTimeSchedule,
    combine,
    preview_occurrences,
)

LONDON = TimeZoneName("Europe/London")
NEW_YORK = TimeZoneName("America/New_York")
SYDNEY = TimeZoneName("Australia/Sydney")


def at_utc(text: str) -> UtcTimestamp:
    """Build a UTC timestamp from an ISO string."""
    return UtcTimestamp(datetime.fromisoformat(text).replace(tzinfo=UTC))


def a_calendar(**overrides: object) -> Calendar:
    """Build a calendar for tests."""
    defaults: dict[str, object] = {
        "calendar_id": CalendarId.generate(),
        "name": "London Settlement",
        "slug": Slug("london-settlement"),
        "timezone": LONDON,
    }
    return Calendar(**(defaults | overrides))  # type: ignore[arg-type]


class TestWeekday:
    def test_named_rather_than_numbered(self) -> None:
        """Sunday is 0 in some cron dialects and 7 in others; names avoid the trap."""
        assert Weekday.MONDAY.value == "monday"

    def test_iso_numbering(self) -> None:
        assert Weekday.MONDAY.iso_number == 1
        assert Weekday.SUNDAY.iso_number == 7

    def test_derives_from_a_date(self) -> None:
        assert Weekday.from_date_object(date(2026, 7, 27)) is Weekday.MONDAY

    def test_working_week_is_monday_to_friday(self) -> None:
        assert Weekday.SATURDAY not in WORKING_WEEK
        assert len(WORKING_WEEK) == 5


class TestIntervalSchedule:
    def test_fires_at_the_configured_interval(self) -> None:
        schedule = IntervalSchedule(every=Duration(900), anchor=at_utc("2026-07-27T00:00:00"))
        assert schedule.next_occurrence_after(at_utc("2026-07-27T00:00:00")) == at_utc(
            "2026-07-27T00:15:00"
        )

    def test_skips_forward_past_a_long_gap(self) -> None:
        """After downtime the next occurrence is the next real one, not a backlog cursor."""
        schedule = IntervalSchedule(every=Duration(900), anchor=at_utc("2026-07-27T00:00:00"))
        assert schedule.next_occurrence_after(at_utc("2026-07-27T02:07:00")) == at_utc(
            "2026-07-27T02:15:00"
        )

    def test_returns_the_anchor_when_asked_before_it(self) -> None:
        schedule = IntervalSchedule(every=Duration(900), anchor=at_utc("2026-07-27T12:00:00"))
        assert schedule.next_occurrence_after(at_utc("2026-07-27T09:00:00")) == at_utc(
            "2026-07-27T12:00:00"
        )

    def test_is_strictly_after(self) -> None:
        """Returning the same instant would make a preview loop forever."""
        schedule = IntervalSchedule(every=Duration(3600), anchor=at_utc("2026-07-27T00:00:00"))
        moment = at_utc("2026-07-27T01:00:00")
        assert schedule.next_occurrence_after(moment).value > moment.value

    def test_rejects_a_zero_interval(self) -> None:
        with pytest.raises(ValidationError):
            IntervalSchedule(every=Duration(0), anchor=at_utc("2026-07-27T00:00:00"))

    def test_interval_is_unaffected_by_dst(self) -> None:
        """ "Every hour" means every hour, whatever the wall clock does."""
        schedule = IntervalSchedule(
            every=Duration(3600), anchor=at_utc("2026-03-29T00:00:00"), timezone=LONDON
        )
        occurrences = preview_occurrences(schedule, after=at_utc("2026-03-29T00:00:00"), count=3)
        gaps = [
            (later.value - earlier.value).total_seconds()
            for earlier, later in zip(occurrences, occurrences[1:], strict=False)
        ]
        assert gaps == [3600.0, 3600.0]


class TestWeekdayTimeScheduleDst:
    """A wall-clock schedule must keep its local meaning across DST transitions."""

    def test_fires_at_the_local_time_before_and_after_a_spring_forward(self) -> None:
        # Europe/London springs forward on 2026-03-29.
        schedule = WeekdayTimeSchedule(at=time(6, 0), weekdays=frozenset(Weekday), timezone=LONDON)
        zone = LONDON.zone_info()

        before = schedule.next_occurrence_after(at_utc("2026-03-27T12:00:00"))
        after = schedule.next_occurrence_after(at_utc("2026-03-30T12:00:00"))

        assert before is not None
        assert after is not None
        assert before.value.astimezone(zone).hour == 6
        assert after.value.astimezone(zone).hour == 6

    def test_utc_instant_shifts_across_a_spring_forward(self) -> None:
        """Same local time, different UTC instant — that is the whole point."""
        schedule = WeekdayTimeSchedule(at=time(6, 0), weekdays=frozenset(Weekday), timezone=LONDON)
        winter = schedule.next_occurrence_after(at_utc("2026-01-15T12:00:00"))
        summer = schedule.next_occurrence_after(at_utc("2026-07-15T12:00:00"))

        assert winter is not None
        assert summer is not None
        assert winter.value.hour != summer.value.hour

    def test_fires_at_the_local_time_across_a_fall_back(self) -> None:
        # Europe/London falls back on 2026-10-25.
        schedule = WeekdayTimeSchedule(at=time(6, 0), weekdays=frozenset(Weekday), timezone=LONDON)
        occurrence = schedule.next_occurrence_after(at_utc("2026-10-25T12:00:00"))
        assert occurrence is not None
        assert occurrence.value.astimezone(LONDON.zone_info()).hour == 6

    @pytest.mark.parametrize("zone", [LONDON, NEW_YORK, SYDNEY])
    def test_local_time_is_preserved_in_every_zone(self, zone: TimeZoneName) -> None:
        """Southern-hemisphere zones transition in the opposite direction."""
        schedule = WeekdayTimeSchedule(at=time(6, 0), weekdays=frozenset(Weekday), timezone=zone)
        occurrences = preview_occurrences(schedule, after=at_utc("2026-01-01T00:00:00"), count=400)
        local_hours = {
            occurrence.value.astimezone(zone.zone_info()).hour for occurrence in occurrences
        }
        assert local_hours == {6}, f"{zone} drifted to hours {sorted(local_hours)}"

    def test_a_nonexistent_local_time_can_be_skipped(self) -> None:
        """01:30 does not exist in London on the spring-forward morning."""
        schedule = WeekdayTimeSchedule(
            at=time(1, 30),
            weekdays=frozenset(Weekday),
            timezone=LONDON,
            skip_nonexistent_times=True,
        )
        occurrences = preview_occurrences(schedule, after=at_utc("2026-03-27T12:00:00"), count=4)
        local_dates = {
            occurrence.value.astimezone(LONDON.zone_info()).date() for occurrence in occurrences
        }
        assert date(2026, 3, 29) not in local_dates

    def test_a_nonexistent_local_time_otherwise_still_fires(self) -> None:
        """The default keeps the work happening, on the right day."""
        schedule = WeekdayTimeSchedule(at=time(1, 30), weekdays=frozenset(Weekday), timezone=LONDON)
        occurrences = preview_occurrences(schedule, after=at_utc("2026-03-27T12:00:00"), count=4)
        local_dates = {
            occurrence.value.astimezone(LONDON.zone_info()).date() for occurrence in occurrences
        }
        assert date(2026, 3, 29) in local_dates


class TestWeekdayTimeSchedule:
    def test_only_fires_on_selected_weekdays(self) -> None:
        schedule = WeekdayTimeSchedule(at=time(6, 0), weekdays=WORKING_WEEK, timezone=LONDON)
        occurrences = preview_occurrences(schedule, after=at_utc("2026-07-24T12:00:00"), count=3)
        weekdays = {
            Weekday.from_date_object(occurrence.value.astimezone(LONDON.zone_info()).date())
            for occurrence in occurrences
        }
        assert weekdays <= WORKING_WEEK

    def test_rejects_an_empty_weekday_set(self) -> None:
        with pytest.raises(ValidationError):
            WeekdayTimeSchedule(at=time(6, 0), weekdays=frozenset(), timezone=LONDON)

    def test_rejects_a_time_carrying_its_own_zone(self) -> None:
        """The zone belongs to the schedule; two sources would be ambiguous."""
        with pytest.raises(ValidationError):
            WeekdayTimeSchedule(at=time(6, 0, tzinfo=UTC), weekdays=WORKING_WEEK, timezone=LONDON)


class TestPreview:
    def test_returns_occurrences_in_order(self) -> None:
        schedule = IntervalSchedule(every=Duration(3600), anchor=at_utc("2026-07-27T00:00:00"))
        occurrences = preview_occurrences(schedule, after=at_utc("2026-07-27T00:00:00"), count=5)
        assert list(occurrences) == sorted(occurrences, key=lambda item: item.value)

    def test_a_manual_schedule_previews_nothing(self) -> None:
        occurrences = preview_occurrences(
            ManualSchedule(), after=at_utc("2026-07-27T00:00:00"), count=5
        )
        assert occurrences == ()

    def test_rejects_a_nonsensical_count(self) -> None:
        schedule = IntervalSchedule(every=Duration(60), anchor=at_utc("2026-07-27T00:00:00"))
        for count in (0, -1, 10_000):
            with pytest.raises(ValidationError):
                preview_occurrences(schedule, after=at_utc("2026-07-27T00:00:00"), count=count)


class TestCronExpression:
    @pytest.mark.parametrize(
        "expression",
        ["0 7 * * 1-5", "*/15 * * * *", "0 0 1 1 *", "0,30 9-17 * * *", "* * * * *"],
    )
    def test_accepts_supported_expressions(self, expression: str) -> None:
        assert CronExpression(expression).expression == expression

    def test_normalises_whitespace(self) -> None:
        assert CronExpression("0   7  *  *  1-5").expression == "0 7 * * 1-5"

    @pytest.mark.parametrize(
        "expression",
        [
            "",
            "0 7 * *",
            "0 7 * * * *",
            "60 7 * * *",
            "0 24 * * *",
            "0 7 32 * *",
            "0 7 * 13 *",
            "0 7 * * 8",
            "0 7 * * mon",
            "5-1 7 * * *",
            "*/0 * * * *",
            "x * * * *",
        ],
    )
    def test_rejects_malformed_or_out_of_range_expressions(self, expression: str) -> None:
        with pytest.raises(ValidationError):
            CronExpression(expression)

    def test_rejects_non_portable_shorthand(self) -> None:
        """`@reboot` and friends cannot be expressed on every target scheduler."""
        for expression in ("@reboot", "@daily", "@yearly"):
            with pytest.raises(ValidationError) as caught:
                CronExpression(expression)
            assert "portable" in caught.value.message

    def test_round_trips(self) -> None:
        expression = CronExpression("0 7 * * 1-5")
        assert CronExpression.from_primitive(expression.to_primitive()) == expression


class TestMisfirePolicy:
    def test_skip_does_not_catch_up(self) -> None:
        assert not MisfirePolicy.SKIP.catches_up

    def test_run_policies_catch_up(self) -> None:
        assert MisfirePolicy.RUN_IMMEDIATELY.catches_up
        assert MisfirePolicy.RUN_ALL.catches_up


class TestCalendar:
    def test_an_ordinary_weekday_is_open(self) -> None:
        verdict = a_calendar().classify(date(2026, 7, 27))
        assert verdict.is_open
        assert verdict.classification is DayClassification.WORKING_DAY

    def test_a_weekend_is_closed(self) -> None:
        assert not a_calendar().is_open(date(2026, 7, 25))

    def test_a_holiday_is_closed(self) -> None:
        calendar = a_calendar(holidays={date(2026, 12, 25): "Christmas Day"})
        verdict = calendar.classify(date(2026, 12, 25))
        assert not verdict.is_open
        assert verdict.note == "Christmas Day"

    def test_a_special_working_day_opens_a_weekend(self) -> None:
        calendar = a_calendar(special_working_days={date(2026, 7, 25): "Year-end run"})
        assert calendar.is_open(date(2026, 7, 25))

    def test_an_early_close_is_still_open(self) -> None:
        calendar = a_calendar(early_closes={date(2026, 12, 24): "Christmas Eve"})
        verdict = calendar.classify(date(2026, 12, 24))
        assert verdict.is_open
        assert verdict.classification is DayClassification.EARLY_CLOSE

    def test_a_holiday_outranks_the_ordinary_week(self) -> None:
        calendar = a_calendar(holidays={date(2026, 7, 27): "Bank holiday"})
        assert not calendar.is_open(date(2026, 7, 27))

    def test_rejects_a_date_that_is_both_holiday_and_working(self) -> None:
        with pytest.raises(ValidationError):
            a_calendar(
                holidays={date(2026, 12, 25): "Christmas"},
                special_working_days={date(2026, 12, 25): "Emergency"},
            )

    def test_rejects_a_holiday_that_is_also_an_early_close(self) -> None:
        """A closed day has no closing time."""
        with pytest.raises(ValidationError):
            a_calendar(
                holidays={date(2026, 12, 25): "Christmas"},
                early_closes={date(2026, 12, 25): "Half day"},
            )

    def test_rejects_a_calendar_that_can_never_be_open(self) -> None:
        with pytest.raises(ValidationError):
            a_calendar(working_weekdays=frozenset())

    def test_a_verdict_names_the_calendar_version_that_decided(self) -> None:
        """Executions from before a calendar change must stay explainable."""
        calendar = a_calendar(
            revision=RevisionNumber(4), holidays={date(2026, 12, 25): "Christmas Day"}
        )
        explanation = calendar.classify(date(2026, 12, 25)).explain()
        assert "revision 4" in explanation
        assert "Christmas Day" in explanation

    def test_supports_testing_a_historical_or_future_date(self) -> None:
        calendar = a_calendar(holidays={date(2019, 12, 25): "Christmas Day"})
        assert not calendar.is_open(date(2019, 12, 25))


class TestConditions:
    def test_an_enabled_switch_allows(self) -> None:
        assert EnabledSwitchFixture.enabled().evaluate().allows

    def test_a_disabled_switch_denies_and_names_itself(self) -> None:
        decision = EnabledSwitchFixture.disabled().evaluate()
        assert not decision.allows
        assert decision.reason_code is not None
        assert decision.reason_code.outcome is ExecutionOutcome.SKIPPED
        assert "maintenance" in decision.explanation

    def test_a_closed_calendar_denies_with_evidence(self) -> None:
        condition = CalendarOpenCondition(
            calendar=a_calendar(holidays={date(2026, 12, 25): "Christmas Day"})
        )
        decision = condition.evaluate(date(2026, 12, 25))
        assert not decision.allows
        assert decision.evidence["classification"] == "holiday"
        assert decision.evidence["calendar_revision"] == 1

    def test_an_open_calendar_allows(self) -> None:
        assert CalendarOpenCondition(calendar=a_calendar()).evaluate(date(2026, 7, 27)).allows

    def test_allowed_weekdays_denies_a_weekend(self) -> None:
        condition = AllowedWeekdaysCondition(weekdays=WORKING_WEEK)
        decision = condition.evaluate(date(2026, 7, 25))
        assert not decision.allows
        assert decision.evidence["weekday"] == "saturday"

    def test_allowed_weekdays_rejects_an_empty_set(self) -> None:
        with pytest.raises(ValidationError):
            AllowedWeekdaysCondition(weekdays=frozenset())

    def test_allowed_environments_denies_the_wrong_environment(self) -> None:
        condition = AllowedEnvironmentsCondition(environments=frozenset({"production"}))
        decision = condition.evaluate("staging")
        assert not decision.allows
        assert decision.reason_code is not None
        assert "production" in decision.explanation

    def test_allowed_environments_rejects_an_empty_set(self) -> None:
        with pytest.raises(ValidationError):
            AllowedEnvironmentsCondition(environments=frozenset())

    def test_a_denial_without_a_reason_code_is_rejected(self) -> None:
        """Without a reason code the resulting skip could not be explained."""
        with pytest.raises(ValidationError):
            ConditionDecision(verdict=ConditionVerdict.DENY, condition_name="anonymous")


class TestEligibility:
    def test_all_allowing_conditions_permit_execution(self) -> None:
        result = combine(
            (
                EnabledSwitchFixture.enabled().evaluate(),
                AllowedWeekdaysCondition(weekdays=WORKING_WEEK).evaluate(date(2026, 7, 27)),
            )
        )
        assert result.allowed
        assert result.outcome() is None

    def test_one_denial_prevents_execution(self) -> None:
        result = combine(
            (
                AllowedWeekdaysCondition(weekdays=WORKING_WEEK).evaluate(date(2026, 7, 27)),
                EnabledSwitchFixture.disabled().evaluate(),
            )
        )
        assert not result.allowed

    def test_the_outcome_follows_the_blocking_reason_code(self) -> None:
        """A calendar closure produces SKIPPED, per ADR 0016."""
        condition = CalendarOpenCondition(
            calendar=a_calendar(holidays={date(2026, 12, 25): "Christmas Day"})
        )
        result = combine((condition.evaluate(date(2026, 12, 25)),))
        assert result.outcome() is ExecutionOutcome.SKIPPED

    def test_an_errored_condition_produces_condition_error(self) -> None:
        """Could-not-tell must never be silently treated as no."""
        result = combine(
            (
                ConditionDecision(
                    verdict=ConditionVerdict.ERROR,
                    condition_name="calendar:remote",
                    reason_code=ReasonCodes.CONDITION_ERROR_CALENDAR_UNAVAILABLE,
                    explanation="The calendar service did not respond.",
                ),
            )
        )
        assert result.outcome() is ExecutionOutcome.CONDITION_ERROR

    def test_the_first_denial_explains_the_result(self) -> None:
        result = combine((EnabledSwitchFixture.disabled().evaluate(),))
        assert "disabled" in result.explain()

    def test_all_decisions_are_retained(self) -> None:
        """An operator may need evidence from conditions after the first failure."""
        decisions = (
            EnabledSwitchFixture.disabled().evaluate(),
            AllowedWeekdaysCondition(weekdays=WORKING_WEEK).evaluate(date(2026, 7, 25)),
        )
        assert len(combine(decisions).to_primitive()["decisions"]) == 2

    def test_no_conditions_means_allowed(self) -> None:
        assert combine(()).allowed


class EnabledSwitchFixture:
    """Switch fixtures, named so the intent reads clearly at the call site."""

    @staticmethod
    def enabled() -> EnabledSwitch:
        return EnabledSwitch(name="settlement-jobs", enabled=True)

    @staticmethod
    def disabled() -> EnabledSwitch:
        return EnabledSwitch(name="settlement-jobs", enabled=False, reason="maintenance window")
