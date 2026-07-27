"""Scheduling: when a task is considered, and whether it is allowed to run.

The two halves are deliberately separate. `schedules` produces candidate times;
`conditions` decides eligibility. A trigger that fires and does not run is a normal,
recorded, explained outcome.
"""

from __future__ import annotations

from taskcontrol.domain.scheduling.calendars import (
    Calendar,
    DayClassification,
    DayVerdict,
)
from taskcontrol.domain.scheduling.conditions import (
    AllowedEnvironmentsCondition,
    AllowedWeekdaysCondition,
    CalendarOpenCondition,
    ConditionDecision,
    ConditionVerdict,
    EligibilityResult,
    EnabledSwitch,
    combine,
)
from taskcontrol.domain.scheduling.schedules import (
    WORKING_WEEK,
    CronExpression,
    IntervalSchedule,
    ManualSchedule,
    MisfirePolicy,
    Schedule,
    Weekday,
    WeekdayTimeSchedule,
    preview_occurrences,
)

__all__ = [
    "WORKING_WEEK",
    "AllowedEnvironmentsCondition",
    "AllowedWeekdaysCondition",
    "Calendar",
    "CalendarOpenCondition",
    "ConditionDecision",
    "ConditionVerdict",
    "CronExpression",
    "DayClassification",
    "DayVerdict",
    "EligibilityResult",
    "EnabledSwitch",
    "IntervalSchedule",
    "ManualSchedule",
    "MisfirePolicy",
    "Schedule",
    "Weekday",
    "WeekdayTimeSchedule",
    "combine",
    "preview_occurrences",
]
