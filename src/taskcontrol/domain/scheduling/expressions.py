"""Turning "every weekday at 06:00" into a cron expression.

The product's claim is that you should not have to write cron syntax to schedule work. That
claim was true of *layout* before it was true of *schedule*: a revision carried a validated
five-field expression, so somebody still had to know what `30 17 * * 1-5` means and, worse,
had to notice when it was wrong.

This module closes that. It is deliberately a **small, closed grammar** rather than natural
language:

| You write | You get |
|---|---|
| `every day at 02:00` | `0 2 * * *` |
| `every weekday at 06:30` | `30 6 * * 1-5` |
| `every weekend at 09:00` | `0 9 * * 0,6` |
| `every monday at 07:00` | `0 7 * * 1` |
| `every monday and thursday at 07:00` | `0 7 * * 1,4` |
| `every hour at minute 15` | `15 * * * *` |
| `every 15 minutes` | `*/15 * * * *` |
| `every 6 hours` | `0 */6 * * *` |
| `on day 1 of every month at 03:00` | `0 3 1 * *` |

Two rules govern everything here.

**No guessing.** Anything outside the grammar is rejected with the forms that *are* accepted.
A scheduler that half-understands "every other Tuesday" and quietly schedules something else
is worse than one that admits it cannot.

**No ambiguity.** `every 7 hours` is refused, because it does not mean what it appears to:
cron's step syntax restarts at midnight, so it would fire at 00:00, 07:00, 14:00, 21:00, and
then again at 00:00 — a three-hour gap once a day. An interval that does not divide its unit
evenly is a trap, so it is not accepted.
"""

from __future__ import annotations

import re
from typing import Final

from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.scheduling.schedules import CronExpression, Weekday

ACCEPTED_FORMS: Final = (
    "every day at HH:MM",
    "every weekday at HH:MM",
    "every weekend at HH:MM",
    "every <weekday> at HH:MM",
    "every <weekday> and <weekday> at HH:MM",
    "every hour at minute MM",
    "every N minutes",
    "every N hours",
    "on day N of every month at HH:MM",
)

_WEEKDAY_NUMBERS: Final[dict[str, int]] = {
    "sunday": 0,
    "monday": 1,
    "tuesday": 2,
    "wednesday": 3,
    "thursday": 4,
    "friday": 5,
    "saturday": 6,
}

WEEKDAY_FIELD: Final = "1-5"
WEEKEND_FIELD: Final = "0,6"

_TIME = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{2})$")

_EVERY_DAY = re.compile(r"^every day at (?P<time>\S+)$")
_EVERY_WEEKDAY = re.compile(r"^every weekday at (?P<time>\S+)$")
_EVERY_WEEKEND = re.compile(r"^every weekend at (?P<time>\S+)$")
_EVERY_NAMED_DAYS = re.compile(r"^every (?P<days>[a-z, and]+?) at (?P<time>\S+)$")
_EVERY_HOUR = re.compile(r"^every hour at minute (?P<minute>\d{1,2})$")
_EVERY_N_MINUTES = re.compile(r"^every (?P<count>\d+) minutes?$")
_EVERY_N_HOURS = re.compile(r"^every (?P<count>\d+) hours?$")
_DAY_OF_MONTH = re.compile(r"^on day (?P<day>\d{1,2}) of every month at (?P<time>\S+)$")

MINUTES_IN_AN_HOUR: Final = 60
HOURS_IN_A_DAY: Final = 24


def parse_schedule_expression(text: str) -> CronExpression:
    """Turn a human schedule expression into a cron expression.

    Args:
        text: The expression, in any casing and with any internal spacing.

    Returns:
        The equivalent cron expression.

    Raises:
        ValidationError: If the expression is outside the accepted grammar, or is inside it
            but means something the author almost certainly did not intend.
    """
    normalised = " ".join(text.lower().split())
    if not normalised:
        raise ValidationError("A schedule expression must not be empty.", details=_help())

    for parse in (
        _parse_every_day,
        _parse_every_weekday,
        _parse_every_weekend,
        _parse_every_hour,
        _parse_every_n_minutes,
        _parse_every_n_hours,
        _parse_day_of_month,
        _parse_named_days,
    ):
        result = parse(normalised)
        if result is not None:
            return result

    raise ValidationError(
        f"'{text}' is not a schedule expression TaskControl understands. It will not guess "
        "at what you meant, because a job that silently runs at a different time than you "
        "asked for is worse than one that fails to be defined.",
        details=_help(),
    )


def _help() -> dict[str, object]:
    """Return the accepted forms, for an error an author can act on."""
    return {"accepted_forms": list(ACCEPTED_FORMS)}


def _parse_time(text: str) -> tuple[int, int]:
    """Parse ``HH:MM``.

    Raises:
        ValidationError: If it is not a 24-hour time.
    """
    match = _TIME.match(text)
    if not match:
        raise ValidationError(
            f"'{text}' is not a time. Write it as HH:MM on a 24-hour clock, such as 06:30 "
            "or 17:00.",
            details=_help(),
        )

    hour, minute = int(match.group("hour")), int(match.group("minute"))
    if hour > HOURS_IN_A_DAY - 1 or minute > MINUTES_IN_AN_HOUR - 1:
        raise ValidationError(f"'{text}' is not a valid time on a 24-hour clock.", details=_help())
    return hour, minute


def _parse_every_day(text: str) -> CronExpression | None:
    """``every day at HH:MM``."""
    match = _EVERY_DAY.match(text)
    if not match:
        return None
    hour, minute = _parse_time(match.group("time"))
    return CronExpression(f"{minute} {hour} * * *")


def _parse_every_weekday(text: str) -> CronExpression | None:
    """``every weekday at HH:MM`` — Monday to Friday."""
    match = _EVERY_WEEKDAY.match(text)
    if not match:
        return None
    hour, minute = _parse_time(match.group("time"))
    return CronExpression(f"{minute} {hour} * * {WEEKDAY_FIELD}")


def _parse_every_weekend(text: str) -> CronExpression | None:
    """``every weekend at HH:MM`` — Saturday and Sunday."""
    match = _EVERY_WEEKEND.match(text)
    if not match:
        return None
    hour, minute = _parse_time(match.group("time"))
    return CronExpression(f"{minute} {hour} * * {WEEKEND_FIELD}")


def _parse_every_hour(text: str) -> CronExpression | None:
    """``every hour at minute MM``."""
    match = _EVERY_HOUR.match(text)
    if not match:
        return None
    minute = int(match.group("minute"))
    if minute > MINUTES_IN_AN_HOUR - 1:
        raise ValidationError(f"There is no minute {minute} in an hour.", details=_help())
    return CronExpression(f"{minute} * * * *")


def _parse_every_n_minutes(text: str) -> CronExpression | None:
    """``every N minutes``, where N divides an hour evenly.

    Raises:
        ValidationError: If the interval does not divide an hour. Cron's step syntax
            restarts at the top of each hour, so ``every 25 minutes`` would fire at :00,
            :25, :50, and then :00 again — a ten-minute gap once an hour. Nobody means that.
    """
    match = _EVERY_N_MINUTES.match(text)
    if not match:
        return None

    count = int(match.group("count"))
    if count < 1 or count > MINUTES_IN_AN_HOUR:
        raise ValidationError("An interval in minutes must be between 1 and 60.", details=_help())
    if MINUTES_IN_AN_HOUR % count:
        raise ValidationError(
            f"'every {count} minutes' does not divide an hour evenly, so cron would not "
            f"space the runs as you expect: it restarts the count at the top of each hour, "
            f"leaving a short gap once an hour. Use an interval that divides 60 — "
            f"{_divisors(MINUTES_IN_AN_HOUR)}.",
            details=_help(),
        )
    if count == MINUTES_IN_AN_HOUR:
        return CronExpression("0 * * * *")
    return CronExpression(f"*/{count} * * * *")


def _parse_every_n_hours(text: str) -> CronExpression | None:
    """``every N hours``, where N divides a day evenly.

    Raises:
        ValidationError: If the interval does not divide 24, for the same reason as minutes.
    """
    match = _EVERY_N_HOURS.match(text)
    if not match:
        return None

    count = int(match.group("count"))
    if count < 1 or count > HOURS_IN_A_DAY:
        raise ValidationError("An interval in hours must be between 1 and 24.", details=_help())
    if HOURS_IN_A_DAY % count:
        raise ValidationError(
            f"'every {count} hours' does not divide a day evenly, so cron would not space "
            f"the runs as you expect: it restarts the count at midnight, leaving a short "
            f"gap once a day. Use an interval that divides 24 — {_divisors(HOURS_IN_A_DAY)}.",
            details=_help(),
        )
    if count == HOURS_IN_A_DAY:
        return CronExpression("0 0 * * *")
    return CronExpression(f"0 */{count} * * *")


def _parse_day_of_month(text: str) -> CronExpression | None:
    """``on day N of every month at HH:MM``.

    Raises:
        ValidationError: If the day is above 28. Days 29 to 31 do not exist in every month,
            so such a schedule would silently skip February — and a monthly job that misses
            a month is exactly the failure nobody notices until an audit.
    """
    match = _DAY_OF_MONTH.match(text)
    if not match:
        return None

    day = int(match.group("day"))
    hour, minute = _parse_time(match.group("time"))

    if day < 1:
        raise ValidationError("There is no day 0 in a month.", details=_help())
    if day > 28:
        raise ValidationError(
            f"Day {day} does not exist in every month, so this schedule would silently "
            "skip the months that are shorter — most obviously February. Use a day between "
            "1 and 28, or express the intent as an end-of-month schedule once TaskControl "
            "supports one.",
            details=_help(),
        )
    return CronExpression(f"{minute} {hour} {day} * *")


def _parse_named_days(text: str) -> CronExpression | None:
    """``every monday at HH:MM`` and ``every monday and thursday at HH:MM``.

    Raises:
        ValidationError: If a named day is not a weekday name, or is repeated.
    """
    match = _EVERY_NAMED_DAYS.match(text)
    if not match:
        return None

    names = [name.strip() for name in match.group("days").replace(" and ", ",").split(",")]
    names = [name for name in names if name]
    if not names or any(name not in _WEEKDAY_NUMBERS for name in names):
        return None

    if len(set(names)) != len(names):
        raise ValidationError(
            "A day is named twice in this schedule. Say each day once.", details=_help()
        )

    hour, minute = _parse_time(match.group("time"))
    days = ",".join(str(number) for number in sorted(_WEEKDAY_NUMBERS[name] for name in names))
    return CronExpression(f"{minute} {hour} * * {days}")


def _divisors(of: int) -> str:
    """Return the usable intervals for a unit, as a readable list."""
    return ", ".join(str(n) for n in range(1, of + 1) if of % n == 0)


def describe(expression: CronExpression) -> str:
    """Return a human description of a cron expression, where one is unambiguous.

    Only the shapes this module produces are described; anything else is returned as the
    expression itself. A confident but wrong paraphrase of somebody's hand-written cron
    would be worse than showing them what they actually wrote.

    Args:
        expression: The cron expression.

    Returns:
        A description, or the expression when it cannot be described faithfully.
    """
    minute, hour, day_of_month, month, day_of_week = expression.to_primitive().split(" ")

    if month != "*":
        return expression.to_primitive()

    if day_of_month != "*" and day_of_week == "*" and minute.isdigit() and hour.isdigit():
        return f"on day {int(day_of_month)} of every month at {int(hour):02d}:{int(minute):02d}"

    if day_of_month != "*":
        return expression.to_primitive()

    if minute.isdigit() and hour == "*":
        return f"every hour at minute {int(minute)}"
    if minute == "0" and hour.startswith("*/"):
        return f"every {hour.removeprefix('*/')} hours"
    if minute.startswith("*/") and hour == "*":
        return f"every {minute.removeprefix('*/')} minutes"

    if not (minute.isdigit() and hour.isdigit()):
        return expression.to_primitive()

    at = f"at {int(hour):02d}:{int(minute):02d}"
    if day_of_week == "*":
        return f"every day {at}"
    if day_of_week == WEEKDAY_FIELD:
        return f"every weekday {at}"
    if day_of_week == WEEKEND_FIELD:
        return f"every weekend {at}"

    names = _weekday_names(day_of_week)
    return f"every {names} {at}" if names else expression.to_primitive()


def _weekday_names(field: str) -> str:
    """Return named days for a simple comma list, or empty when it is not one."""
    if not all(part.isdigit() for part in field.split(",")):
        return ""

    numbers = [int(part) for part in field.split(",")]
    if any(number > len(Weekday) - 1 for number in numbers):
        return ""

    by_number = {number: name for name, number in _WEEKDAY_NUMBERS.items()}
    names = [by_number[number] for number in numbers]
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} and {names[-1]}"
