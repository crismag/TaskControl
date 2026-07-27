"""The schedule grammar, and the two things it refuses to do.

The product claims you should not have to write cron syntax. That claim was true of layout
before it was true of schedule, and this module is what makes the second half true.

It is a closed grammar on purpose. The tests below are as much about what it declines as
what it accepts, because a scheduler that half-understands an expression and quietly
schedules something else is worse than one that admits it cannot.
"""

from __future__ import annotations

import pytest

from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.scheduling.expressions import (
    ACCEPTED_FORMS,
    describe,
    parse_schedule_expression,
)

ACCEPTED = [
    ("every day at 02:00", "0 2 * * *"),
    ("every day at 00:00", "0 0 * * *"),
    ("every weekday at 06:30", "30 6 * * 1-5"),
    ("every weekend at 09:00", "0 9 * * 0,6"),
    ("every monday at 07:00", "0 7 * * 1"),
    ("every sunday at 23:45", "45 23 * * 0"),
    ("every monday and thursday at 07:00", "0 7 * * 1,4"),
    ("every tuesday, wednesday and friday at 18:00", "0 18 * * 2,3,5"),
    ("every hour at minute 15", "15 * * * *"),
    ("every 15 minutes", "*/15 * * * *"),
    ("every 1 minute", "*/1 * * * *"),
    ("every 60 minutes", "0 * * * *"),
    ("every 6 hours", "0 */6 * * *"),
    ("every 24 hours", "0 0 * * *"),
    ("on day 1 of every month at 03:00", "0 3 1 * *"),
    ("on day 28 of every month at 23:59", "59 23 28 * *"),
]


@pytest.mark.parametrize(("expression", "cron"), ACCEPTED)
def test_accepted_expressions_produce_the_expected_cron(expression: str, cron: str) -> None:
    assert parse_schedule_expression(expression).to_primitive() == cron


@pytest.mark.parametrize(("expression", "cron"), ACCEPTED)
def test_parsing_is_deterministic(expression: str, cron: str) -> None:
    """The same words always mean the same thing. Deployment digests depend on it."""
    del cron
    assert parse_schedule_expression(expression) == parse_schedule_expression(expression)


def test_casing_and_spacing_do_not_matter() -> None:
    """People type how they type. This is not the place to be strict."""
    assert parse_schedule_expression("  Every   Weekday  at  06:30 ") == parse_schedule_expression(
        "every weekday at 06:30"
    )


class TestRefusals:
    """Refusing is a feature. Each of these has a specific reason."""

    def test_an_interval_that_does_not_divide_an_hour_is_refused(self) -> None:
        """'every 25 minutes' fires at :00, :25, :50, then :00 — a ten-minute gap hourly.

        Cron restarts the step at the top of the hour. Nobody who writes this means it.
        """
        with pytest.raises(ValidationError, match="does not divide an hour"):
            parse_schedule_expression("every 25 minutes")

    def test_an_interval_that_does_not_divide_a_day_is_refused(self) -> None:
        """Same trap, one unit up: 'every 7 hours' has a three-hour gap once a day."""
        with pytest.raises(ValidationError, match="does not divide a day"):
            parse_schedule_expression("every 7 hours")

    def test_the_refusal_says_which_intervals_do_work(self) -> None:
        """An error an author cannot act on has done half a job."""
        with pytest.raises(ValidationError) as raised:
            parse_schedule_expression("every 7 hours")
        assert "1, 2, 3, 4, 6, 8, 12, 24" in str(raised.value)

    def test_a_day_that_does_not_exist_in_every_month_is_refused(self) -> None:
        """Day 31 silently skips February — a monthly job nobody notices missing."""
        with pytest.raises(ValidationError, match="does not exist in every month"):
            parse_schedule_expression("on day 31 of every month at 03:00")

    def test_something_outside_the_grammar_is_refused_rather_than_guessed(self) -> None:
        with pytest.raises(ValidationError, match="not a schedule expression"):
            parse_schedule_expression("every other tuesday at 09:00")

    def test_the_refusal_lists_what_is_accepted(self) -> None:
        with pytest.raises(ValidationError) as raised:
            parse_schedule_expression("whenever")
        assert raised.value.details["accepted_forms"] == list(ACCEPTED_FORMS)

    def test_an_impossible_time_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="24-hour clock"):
            parse_schedule_expression("every day at 25:00")

    def test_a_repeated_day_is_refused(self) -> None:
        """Almost always a typo for a different day, and never worth guessing which."""
        with pytest.raises(ValidationError, match="named twice"):
            parse_schedule_expression("every monday and monday at 07:00")

    def test_an_empty_expression_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            parse_schedule_expression("   ")


class TestDescribe:
    @pytest.mark.parametrize(("expression", "cron"), ACCEPTED)
    def test_every_accepted_expression_reads_back(self, expression: str, cron: str) -> None:
        """What you wrote comes back out, so a plan can show it to you.

        Not necessarily word for word — casing and separators are normalised — but it must
        parse back to the same schedule, which is the property that matters.
        """
        del expression
        from taskcontrol.domain.scheduling.schedules import CronExpression

        described = describe(CronExpression(cron))
        assert parse_schedule_expression(described).to_primitive() == cron

    def test_an_expression_it_cannot_describe_is_returned_unchanged(self) -> None:
        """A confident wrong paraphrase of somebody's hand-written cron is worse than none."""
        from taskcontrol.domain.scheduling.schedules import CronExpression

        obscure = CronExpression("5 4 3 2 1")
        assert describe(obscure) == "5 4 3 2 1"
