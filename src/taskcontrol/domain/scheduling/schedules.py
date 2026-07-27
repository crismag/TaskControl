"""When a task is *considered* for execution.

A schedule produces candidate trigger times. It does not decide whether the task actually
runs — that is eligibility, and it lives in :mod:`taskcontrol.domain.scheduling.conditions`.
Keeping the two apart is the distinction the whole product is built on: a trigger fired and
the task was skipped is a normal, recordable, explainable outcome.

Everything here is timezone-aware and DST-correct. A schedule that means 06:00 local keeps
meaning 06:00 local across a daylight-saving transition, which is why schedules store an
IANA zone name rather than an offset.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from typing import Any, Protocol, Self

from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.common.values import Duration, TimeZoneName, UtcTimestamp

MAX_PREVIEW_OCCURRENCES = 500
_SEARCH_LIMIT_DAYS = 1500

_CRON_FIELD_COUNT = 5


class Weekday(StrEnum):
    """A day of the week, named rather than numbered.

    Numbering is the classic cron trap — Sunday is 0 in some dialects and 7 in others.
    Names remove the ambiguity from the domain entirely.
    """

    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"

    @property
    def iso_number(self) -> int:
        """ISO weekday number, Monday = 1 through Sunday = 7."""
        return _WEEKDAY_ORDER.index(self) + 1

    @classmethod
    def from_datetime(cls, moment: datetime) -> Weekday:
        """Return the weekday of a datetime.

        Args:
            moment: The datetime to inspect, in whatever zone it carries. Convert to the
                intended local zone first: the weekday of an instant depends on where
                you are standing.

        Returns:
            The weekday.
        """
        return _WEEKDAY_ORDER[moment.isoweekday() - 1]

    @classmethod
    def from_date_object(cls, day: date) -> Weekday:
        """Return the weekday of a calendar date.

        Args:
            day: The date to inspect.

        Returns:
            The weekday.
        """
        return _WEEKDAY_ORDER[day.weekday()]


_WEEKDAY_ORDER: tuple[Weekday, ...] = (
    Weekday.MONDAY,
    Weekday.TUESDAY,
    Weekday.WEDNESDAY,
    Weekday.THURSDAY,
    Weekday.FRIDAY,
    Weekday.SATURDAY,
    Weekday.SUNDAY,
)

WORKING_WEEK: frozenset[Weekday] = frozenset(_WEEKDAY_ORDER[:5])
"""Monday to Friday. A convenience, not a business calendar — that is `Calendar`."""


class MisfirePolicy(StrEnum):
    """What to do about occurrences missed while TaskControl was not running.

    A scheduled-task product must answer this explicitly. Silence here is how a nightly
    job quietly stops happening after a restart.
    """

    RUN_IMMEDIATELY = "run_immediately"
    "Run the most recent missed occurrence once, then resume normally."

    RUN_ALL = "run_all"
    "Run every missed occurrence. Only safe for genuinely idempotent work."

    SKIP = "skip"
    "Record the misfires and wait for the next occurrence."

    @property
    def catches_up(self) -> bool:
        """Whether missed occurrences produce executions."""
        return self is not MisfirePolicy.SKIP


class Schedule(Protocol):
    """A source of candidate trigger times.

    Implementations are value objects. Every one must be able to answer "when next, after
    this instant" without consulting a clock — the instant is always supplied, so previews,
    tests, and replays all take the same path as live scheduling.
    """

    timezone: TimeZoneName

    def next_occurrence_after(self, moment: UtcTimestamp) -> UtcTimestamp | None:
        """Return the first candidate strictly after a given instant.

        Args:
            moment: The instant to search from.

        Returns:
            The next candidate, or ``None`` if the schedule has no further occurrences.
        """
        ...

    def to_primitive(self) -> dict[str, Any]:
        """Return a stable representation."""
        ...


def preview_occurrences(
    schedule: Schedule, *, after: UtcTimestamp, count: int
) -> tuple[UtcTimestamp, ...]:
    """Return the next occurrences of a schedule.

    The preview a user sees and the times the scheduler fires come from the same function,
    so a preview cannot drift from reality.

    Args:
        schedule: The schedule to preview.
        after: The instant to start from.
        count: How many occurrences to return.

    Returns:
        Up to ``count`` occurrences, in order. Shorter when the schedule ends.

    Raises:
        ValidationError: If ``count`` is not a sensible preview size.
    """
    if count < 1:
        raise ValidationError("Preview count must be at least 1.", details={"count": count})
    if count > MAX_PREVIEW_OCCURRENCES:
        raise ValidationError(
            "Preview count exceeds the supported maximum.",
            details={"count": count, "maximum": MAX_PREVIEW_OCCURRENCES},
        )

    occurrences: list[UtcTimestamp] = []
    cursor = after
    for _ in range(count):
        nxt = schedule.next_occurrence_after(cursor)
        if nxt is None:
            break
        occurrences.append(nxt)
        cursor = nxt
    return tuple(occurrences)


@dataclass(frozen=True, slots=True)
class IntervalSchedule:
    """Fires at a fixed interval from an anchor instant.

    Interval schedules are wall-clock-independent: "every 15 minutes" means every 15
    minutes, and a DST transition does not change that. This is the right choice for
    polling and the wrong choice for "the 06:00 report".

    Attributes:
        every: The interval between occurrences.
        anchor: The instant the series is measured from.
        timezone: Retained for display. It does not affect the arithmetic.
    """

    every: Duration
    anchor: UtcTimestamp
    timezone: TimeZoneName = field(default_factory=TimeZoneName.utc)

    def __post_init__(self) -> None:
        """Validate the interval.

        Raises:
            ValidationError: If the interval is zero, which would fire endlessly.
        """
        if self.every.is_zero:
            raise ValidationError(
                "An interval schedule requires a non-zero interval.",
            )

    def next_occurrence_after(self, moment: UtcTimestamp) -> UtcTimestamp:
        """Return the first occurrence strictly after a given instant.

        Args:
            moment: The instant to search from.

        Returns:
            The next occurrence.
        """
        step = self.every.as_timedelta()
        if moment.value < self.anchor.value:
            return self.anchor

        elapsed = moment.value - self.anchor.value
        completed = int(elapsed.total_seconds() // step.total_seconds())
        candidate = self.anchor.value + step * (completed + 1)
        return UtcTimestamp(candidate)

    def to_primitive(self) -> dict[str, Any]:
        """Return a stable representation."""
        return {
            "type": "interval",
            "every_seconds": self.every.to_primitive(),
            "anchor": self.anchor.to_primitive(),
            "timezone": self.timezone.to_primitive(),
        }


@dataclass(frozen=True, slots=True)
class WeekdayTimeSchedule:
    """Fires at a local wall-clock time on chosen weekdays.

    This is the schedule most operational work actually wants: "06:00 on weekdays, London
    time" keeps meaning 06:00 in London when the clocks change.

    DST is handled explicitly rather than left to chance. On a spring-forward day the
    nominated time may not exist, and on a fall-back day it may exist twice. See
    :attr:`skip_nonexistent_times`.

    Attributes:
        at: The local wall-clock time.
        weekdays: Which days it fires on.
        timezone: The zone the wall-clock time is interpreted in.
        skip_nonexistent_times: When the local time is skipped by a spring-forward
            transition, skip that day rather than firing at the shifted instant.
    """

    at: time
    weekdays: frozenset[Weekday]
    timezone: TimeZoneName
    skip_nonexistent_times: bool = False

    def __post_init__(self) -> None:
        """Validate the schedule.

        Raises:
            ValidationError: If no weekday is selected, or the time carries its own zone.
        """
        if not self.weekdays:
            raise ValidationError(
                "A weekday schedule must select at least one day, or it can never fire.",
            )
        if self.at.tzinfo is not None:
            raise ValidationError(
                "The time of day must be a plain wall-clock time. Its zone comes from the "
                "schedule's timezone field.",
            )

    def next_occurrence_after(self, moment: UtcTimestamp) -> UtcTimestamp | None:
        """Return the first occurrence strictly after a given instant.

        Args:
            moment: The instant to search from.

        Returns:
            The next occurrence, or ``None`` if none was found within the search horizon.
        """
        zone = self.timezone.zone_info()
        local_now = moment.value.astimezone(zone)

        for offset in range(_SEARCH_LIMIT_DAYS):
            local_date = (local_now + timedelta(days=offset)).date()
            if Weekday.from_date_object(local_date) not in self.weekdays:
                continue

            naive = datetime.combine(local_date, self.at)
            localised = naive.replace(tzinfo=zone)

            # A local time skipped by a spring-forward transition does not round-trip:
            # converting to UTC and back yields a different wall clock. When it does not
            # exist and the schedule says so, skip the day; otherwise fire at the shifted
            # instant, because the work still needs to happen on that day.
            # Round-tripping through UTC is required: `astimezone` on a datetime already
            # in the target zone is a no-op and would never reveal the shift.
            round_tripped = localised.astimezone(UTC).astimezone(zone)
            does_not_exist = (
                round_tripped.hour != self.at.hour or round_tripped.minute != self.at.minute
            )
            if does_not_exist and self.skip_nonexistent_times:
                continue

            candidate = UtcTimestamp(localised)
            if candidate.value > moment.value:
                return candidate

        return None

    def to_primitive(self) -> dict[str, Any]:
        """Return a stable representation."""
        return {
            "type": "weekday_time",
            "at": self.at.isoformat(),
            "weekdays": sorted(day.value for day in self.weekdays),
            "timezone": self.timezone.to_primitive(),
            "skip_nonexistent_times": self.skip_nonexistent_times,
        }


@dataclass(frozen=True, slots=True)
class CronExpression:
    """A validated five-field cron expression.

    Held as a value object so a malformed expression is rejected when the revision is
    written, not at 03:00 when it was supposed to fire.

    Only the subset TaskControl guarantees across scheduler adapters is accepted: minute,
    hour, day-of-month, month, and day-of-week, with ``*``, lists, ranges, and steps.
    Dialect extensions such as ``@reboot`` or ``L`` are rejected, because they cannot be
    expressed identically on every target the product intends to support.

    Attributes:
        expression: The normalised expression text.
    """

    expression: str

    def __post_init__(self) -> None:
        """Validate the expression.

        Raises:
            ValidationError: If the expression is malformed or uses an unsupported
                extension.
        """
        if not isinstance(self.expression, str) or not self.expression.strip():
            raise ValidationError("A cron expression must not be empty.")

        text = " ".join(self.expression.split())
        if text.startswith("@"):
            raise ValidationError(
                "Shorthand cron expressions are not supported, because they are not "
                "portable across schedulers. Write the five fields explicitly.",
                details={"expression": self.expression},
            )

        fields = text.split(" ")
        if len(fields) != _CRON_FIELD_COUNT:
            raise ValidationError(
                "A cron expression must have exactly five fields: "
                "minute hour day-of-month month day-of-week.",
                details={"expression": self.expression, "field_count": len(fields)},
            )

        for value, (name, low, high) in zip(fields, _CRON_FIELDS, strict=True):
            _validate_cron_field(value, name, low, high)

        object.__setattr__(self, "expression", text)

    def to_primitive(self) -> str:
        """Return the normalised expression."""
        return self.expression

    @classmethod
    def from_primitive(cls, value: Any) -> Self:
        """Build from a stored expression."""
        return cls(value)

    def __str__(self) -> str:
        """Return the normalised expression."""
        return self.expression


_CRON_FIELDS: tuple[tuple[str, int, int], ...] = (
    ("minute", 0, 59),
    ("hour", 0, 23),
    ("day-of-month", 1, 31),
    ("month", 1, 12),
    ("day-of-week", 0, 6),
)

_CRON_TERM = re.compile(r"^(\*|\d+(-\d+)?)(/\d+)?$")


def _validate_cron_field(value: str, name: str, low: int, high: int) -> None:
    """Validate one cron field against its permitted range.

    Args:
        value: The field text.
        name: The field's name, for error messages.
        low: Lowest permitted value.
        high: Highest permitted value.

    Raises:
        ValidationError: If the field is malformed or out of range.
    """
    for term in value.split(","):
        if not term or not _CRON_TERM.match(term):
            raise ValidationError(
                f"Malformed {name} field in cron expression.",
                details={"field": name, "term": term},
            )

        body, _, step = term.partition("/")
        if step and int(step) < 1:
            raise ValidationError(
                f"Step in the {name} field must be at least 1.",
                details={"field": name, "term": term},
            )

        if body == "*":
            continue

        start, _, end = body.partition("-")
        bounds = [int(start)] + ([int(end)] if end else [])
        for bound in bounds:
            if not low <= bound <= high:
                raise ValidationError(
                    f"Value in the {name} field is outside the permitted range {low}-{high}.",
                    details={"field": name, "value": bound},
                )
        if end and int(end) < int(start):
            raise ValidationError(
                f"Range in the {name} field ends before it starts.",
                details={"field": name, "term": term},
            )


@dataclass(frozen=True, slots=True)
class ManualSchedule:
    """No automatic occurrences. The task runs only when someone asks.

    A first-class schedule rather than the absence of one, so that "this task is manual"
    is a recorded decision rather than an empty field that might be an oversight.

    Attributes:
        timezone: Retained for display consistency.
    """

    timezone: TimeZoneName = field(default_factory=TimeZoneName.utc)

    def next_occurrence_after(self, moment: UtcTimestamp) -> None:
        """Return ``None``: a manual schedule never fires on its own.

        Args:
            moment: Ignored.

        Returns:
            Always ``None``.
        """
        _ = moment
        return

    def to_primitive(self) -> dict[str, Any]:
        """Return a stable representation."""
        return {"type": "manual", "timezone": self.timezone.to_primitive()}
