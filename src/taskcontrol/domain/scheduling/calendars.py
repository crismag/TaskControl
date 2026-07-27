"""Business calendars: which days operations actually happen.

A calendar answers "is this date a working day for this business", which is not the same
question as "is this a weekday". Settlement runs on a bank's calendar, payroll on the
company's, and market data on an exchange's — and none of them agree.

Calendars are versioned and carry provenance because they change. When a government
announces a new bank holiday, executions from before the change must still be explainable
against the calendar that was in force at the time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any

from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.common.identifiers import CalendarId
from taskcontrol.domain.common.values import RevisionNumber, Slug, TimeZoneName
from taskcontrol.domain.scheduling.schedules import WORKING_WEEK, Weekday


class DayClassification(StrEnum):
    """Why a date is or is not a working day."""

    WORKING_DAY = "working_day"
    "An ordinary working day."

    WEEKEND = "weekend"
    "Not a configured working weekday."

    HOLIDAY = "holiday"
    "A configured holiday or exceptional closure."

    SPECIAL_WORKING_DAY = "special_working_day"
    "Explicitly opened despite falling outside the working week."

    EARLY_CLOSE = "early_close"
    "Open, but ending earlier than usual."

    @property
    def is_open(self) -> bool:
        """Whether operations run on a day with this classification."""
        return self in {
            DayClassification.WORKING_DAY,
            DayClassification.SPECIAL_WORKING_DAY,
            DayClassification.EARLY_CLOSE,
        }


@dataclass(frozen=True, slots=True)
class DayVerdict:
    """Whether a specific date is open, and why.

    Attributes:
        day: The date evaluated.
        classification: How the date was classified.
        calendar_name: Which calendar decided.
        calendar_revision: Which version of that calendar decided.
        note: Any label attached to the date, such as a holiday name.
    """

    day: date
    classification: DayClassification
    calendar_name: str
    calendar_revision: RevisionNumber
    note: str | None = None

    @property
    def is_open(self) -> bool:
        """Whether operations run on this date."""
        return self.classification.is_open

    def explain(self) -> str:
        """Return a human-readable explanation of the verdict.

        Returns:
            A sentence naming the date, the outcome, the reason, and the calendar
            version that decided — enough to reconstruct the decision later.
        """
        state = "open" if self.is_open else "closed"
        reason = f" ({self.note})" if self.note else ""
        return (
            f"{self.day.isoformat()} is {state}: {self.classification.value}{reason}, "
            f"per calendar {self.calendar_name!r} revision {self.calendar_revision}."
        )

    def to_primitive(self) -> dict[str, Any]:
        """Return a stable representation."""
        return {
            "day": self.day.isoformat(),
            "classification": str(self.classification),
            "is_open": self.is_open,
            "calendar": self.calendar_name,
            "calendar_revision": self.calendar_revision.to_primitive(),
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class Calendar:
    """A named set of operating days, versioned and attributable.

    Attributes:
        calendar_id: Stable identifier.
        name: Human-readable name.
        slug: Stable reference name.
        timezone: The zone dates are interpreted in.
        revision: Which version of this calendar's content this is.
        working_weekdays: The ordinary working week.
        holidays: Dates that are closed, mapped to their names.
        special_working_days: Dates open despite falling outside the working week.
        early_closes: Dates that are open but end early, mapped to their reasons.
        source: Where the calendar data came from, for provenance.
    """

    calendar_id: CalendarId
    name: str
    slug: Slug
    timezone: TimeZoneName
    revision: RevisionNumber = field(default_factory=RevisionNumber.first)
    working_weekdays: frozenset[Weekday] = field(default_factory=lambda: WORKING_WEEK)
    holidays: dict[date, str] = field(default_factory=dict)
    special_working_days: dict[date, str] = field(default_factory=dict)
    early_closes: dict[date, str] = field(default_factory=dict)
    source: str = ""

    def __post_init__(self) -> None:
        """Validate the calendar.

        Raises:
            ValidationError: If the calendar can never be open, or a date is classified
                two contradictory ways.
        """
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValidationError("A calendar requires a name.")

        if not self.working_weekdays and not self.special_working_days:
            raise ValidationError(
                "A calendar with no working weekdays and no special working days is "
                "never open, so nothing bound to it could ever run.",
                details={"calendar": self.name},
            )

        contradictions = sorted(set(self.holidays) & set(self.special_working_days))
        if contradictions:
            raise ValidationError(
                "A date cannot be both a holiday and a special working day.",
                details={
                    "calendar": self.name,
                    "dates": [day.isoformat() for day in contradictions],
                },
            )

        early_holidays = sorted(set(self.holidays) & set(self.early_closes))
        if early_holidays:
            raise ValidationError(
                "A date cannot be both a holiday and an early close: a closed day has "
                "no closing time.",
                details={
                    "calendar": self.name,
                    "dates": [day.isoformat() for day in early_holidays],
                },
            )

    def classify(self, day: date) -> DayVerdict:
        """Classify one date against this calendar.

        Precedence is deliberate and ordered from most specific to least: an explicit
        holiday beats a special working day beats an early close beats the ordinary
        working week.

        Args:
            day: The date to classify.

        Returns:
            The verdict, carrying the calendar version that produced it.
        """
        if (note := self.holidays.get(day)) is not None:
            return self._verdict(day, DayClassification.HOLIDAY, note)

        if (note := self.special_working_days.get(day)) is not None:
            return self._verdict(day, DayClassification.SPECIAL_WORKING_DAY, note)

        if (note := self.early_closes.get(day)) is not None:
            return self._verdict(day, DayClassification.EARLY_CLOSE, note)

        weekday = Weekday.from_date_object(day)
        if weekday not in self.working_weekdays:
            return self._verdict(day, DayClassification.WEEKEND, None)

        return self._verdict(day, DayClassification.WORKING_DAY, None)

    def is_open(self, day: date) -> bool:
        """Whether operations run on a date.

        Args:
            day: The date to check.

        Returns:
            ``True`` when the calendar is open.
        """
        return self.classify(day).is_open

    def _verdict(
        self, day: date, classification: DayClassification, note: str | None
    ) -> DayVerdict:
        """Build a verdict stamped with this calendar's identity and version."""
        return DayVerdict(
            day=day,
            classification=classification,
            calendar_name=self.name,
            calendar_revision=self.revision,
            note=note,
        )

    def to_primitive(self) -> dict[str, Any]:
        """Return a stable representation."""
        return {
            "calendar_id": self.calendar_id.to_primitive(),
            "name": self.name,
            "slug": self.slug.to_primitive(),
            "timezone": self.timezone.to_primitive(),
            "revision": self.revision.to_primitive(),
            "working_weekdays": sorted(day.value for day in self.working_weekdays),
            "holidays": {day.isoformat(): note for day, note in sorted(self.holidays.items())},
            "special_working_days": {
                day.isoformat(): note for day, note in sorted(self.special_working_days.items())
            },
            "early_closes": {
                day.isoformat(): note for day, note in sorted(self.early_closes.items())
            },
            "source": self.source,
        }
