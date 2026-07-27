"""Value objects and identifiers shared across the domain.

Nothing here knows about persistence, transport, or scheduling. These are the types every
other domain module is built from, and each one refuses to hold an invalid value.
"""

from __future__ import annotations

from taskcontrol.domain.common.identifiers import (
    AttemptId,
    CalendarId,
    CollectionId,
    EntityId,
    ExecutionId,
    OwnerId,
    ProfileId,
    RunConditionId,
    ScheduleId,
    TargetId,
    TaskId,
    TaskRevisionId,
    generate_uuid7,
)
from taskcontrol.domain.common.tracing import CorrelationId, IdempotencyKey
from taskcontrol.domain.common.values import (
    ContentDigest,
    Duration,
    RevisionNumber,
    SchemaVersion,
    SecretReference,
    Slug,
    TimeZoneName,
    UtcTimestamp,
)

__all__ = [
    "AttemptId",
    "CalendarId",
    "CollectionId",
    "ContentDigest",
    "CorrelationId",
    "Duration",
    "EntityId",
    "ExecutionId",
    "IdempotencyKey",
    "OwnerId",
    "ProfileId",
    "RevisionNumber",
    "RunConditionId",
    "ScheduleId",
    "SchemaVersion",
    "SecretReference",
    "Slug",
    "TargetId",
    "TaskId",
    "TaskRevisionId",
    "TimeZoneName",
    "UtcTimestamp",
    "generate_uuid7",
]
