"""Explicit translation between domain objects and storage records.

Written by hand rather than generated. A mapper is where a storage decision meets a domain
invariant, and the two should be forced to agree in code someone can read — an automatic
mapping would silently paper over the places where the shapes genuinely differ.

The timezone rule is enforced here in both directions: a naive datetime never reaches the
domain, and an aware one never reaches the database.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from taskcontrol.adapters.persistence.models import (
    ExecutionAttemptRecord,
    ExecutionRecord,
    TaskRecord,
    TaskRevisionRecord,
)
from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.common.identifiers import (
    AttemptId,
    ExecutionId,
    OwnerId,
    TaskId,
    TaskRevisionId,
)
from taskcontrol.domain.common.tracing import CorrelationId, IdempotencyKey
from taskcontrol.domain.common.values import (
    ContentDigest,
    Duration,
    RevisionNumber,
    SchemaVersion,
    Slug,
    UtcTimestamp,
)
from taskcontrol.domain.deployment.strategies import DeploymentSpecification
from taskcontrol.domain.execution.execution import (
    Execution,
    ExecutionAttempt,
    TriggerSource,
)
from taskcontrol.domain.execution.results import (
    ProcessResult,
    TerminationCause,
    TerminationMode,
)
from taskcontrol.domain.execution.vocabulary import (
    ExecutionOutcome,
    ExecutionState,
    ReasonCode,
)
from taskcontrol.domain.scheduling.schedules import CronExpression
from taskcontrol.domain.tasks.actions import ActionSpecification
from taskcontrol.domain.tasks.lifecycle import PublicationState, TaskLifecycleState
from taskcontrol.domain.tasks.revision import ExecutionControls, TaskRevision
from taskcontrol.domain.tasks.task import Task


def to_naive_utc(timestamp: UtcTimestamp | None) -> datetime | None:
    """Return a storage-ready datetime.

    SQLite cannot store an offset, so an aware datetime written there round-trips as a
    lie. Everything is normalised to UTC and stripped, and :func:`from_naive_utc` puts UTC
    back on the way out.

    Args:
        timestamp: The domain timestamp, or ``None``.

    Returns:
        A naive UTC datetime, or ``None``.
    """
    if timestamp is None:
        return None
    return timestamp.value.astimezone(UTC).replace(tzinfo=None)


def from_naive_utc(value: datetime | None) -> UtcTimestamp | None:
    """Return a domain timestamp from a stored datetime.

    Args:
        value: The stored datetime, assumed UTC.

    Returns:
        The timestamp, or ``None``.

    Raises:
        ValidationError: If the stored value unexpectedly carries an offset, which would
            mean something wrote through a path that bypassed :func:`to_naive_utc`.
    """
    if value is None:
        return None
    if value.tzinfo is not None:
        return UtcTimestamp(value)
    return UtcTimestamp(value.replace(tzinfo=UTC))


def _require(value: Any, field: str) -> Any:
    """Return a stored value that must be present.

    Args:
        value: The value read from a record.
        field: The field name, for the error message.

    Returns:
        The value.

    Raises:
        ValidationError: If it is missing, which means the row is corrupt.
    """
    if value is None:
        raise ValidationError(
            "A stored record is missing a required field.", details={"field": field}
        )
    return value


def task_to_record(task: Task, *, storage_version: int = 1) -> TaskRecord:
    """Build a storage record from a task.

    Args:
        task: The domain task.
        storage_version: The optimistic-concurrency counter to store.

    Returns:
        The record.
    """
    return TaskRecord(
        task_id=task.task_id.to_primitive(),
        slug=task.slug.to_primitive(),
        name=task.name,
        description=task.description,
        owner_id=task.owner_id.to_primitive(),
        lifecycle_state=str(task.lifecycle_state),
        active_revision_id=(
            task.active_revision_id.to_primitive() if task.active_revision_id else None
        ),
        labels={"values": sorted(task.labels)},
        created_at=to_naive_utc(task.created_at),
        created_by=task.created_by.to_primitive(),
        updated_at=to_naive_utc(task.updated_at),
        updated_by=task.updated_by.to_primitive() if task.updated_by else None,
        storage_version=storage_version,
    )


def apply_task_to_record(record: TaskRecord, task: Task) -> None:
    """Copy a task's mutable state onto an existing record.

    Identifier and creation metadata are deliberately not copied: they are immutable, and
    writing them again would let a bug rewrite history.

    Args:
        record: The record to update.
        task: The task carrying the new state.
    """
    record.slug = task.slug.to_primitive()
    record.name = task.name
    record.description = task.description
    record.owner_id = task.owner_id.to_primitive()
    record.lifecycle_state = str(task.lifecycle_state)
    record.active_revision_id = (
        task.active_revision_id.to_primitive() if task.active_revision_id else None
    )
    record.labels = {"values": sorted(task.labels)}
    record.updated_at = to_naive_utc(task.updated_at)
    record.updated_by = task.updated_by.to_primitive() if task.updated_by else None


def record_to_task(record: TaskRecord) -> Task:
    """Build a domain task from a storage record.

    Args:
        record: The stored record.

    Returns:
        The task.

    Raises:
        ValidationError: If the record is corrupt or violates a domain invariant. Failing
            loudly here is correct: silently repairing a bad row would hide the corruption.
    """
    labels = record.labels or {}
    return Task(
        task_id=TaskId(record.task_id),
        name=record.name,
        slug=Slug(record.slug),
        owner_id=OwnerId(record.owner_id),
        created_at=_require(from_naive_utc(record.created_at), "created_at"),
        created_by=OwnerId(record.created_by),
        description=record.description,
        lifecycle_state=TaskLifecycleState(record.lifecycle_state),
        active_revision_id=(
            TaskRevisionId(record.active_revision_id) if record.active_revision_id else None
        ),
        labels=frozenset(labels.get("values", ())),
        updated_at=from_naive_utc(record.updated_at),
        updated_by=OwnerId(record.updated_by) if record.updated_by else None,
    )


def revision_content(revision: TaskRevision) -> dict[str, Any]:
    """Return the JSON payload stored for a revision.

    Exactly the fields that define execution meaning, in the same shape the content digest
    is computed over — so a stored revision can be verified against its digest without
    reconstructing a domain object.

    Args:
        revision: The revision.

    Returns:
        The payload.
    """
    return {
        "action": revision.action.to_primitive(),
        "controls": revision.controls.to_primitive(),
        "deployment": revision.deployment.to_primitive(),
        "activation_schedule": (
            revision.activation_schedule.to_primitive() if revision.activation_schedule else None
        ),
    }


def revision_to_record(revision: TaskRevision) -> TaskRevisionRecord:
    """Build a storage record from a revision.

    Args:
        revision: The domain revision.

    Returns:
        The record.
    """
    return TaskRevisionRecord(
        revision_id=revision.revision_id.to_primitive(),
        task_id=revision.task_id.to_primitive(),
        revision_number=revision.revision_number.to_primitive(),
        schema_version=revision.schema_version.to_primitive(),
        publication_state=str(revision.publication_state),
        change_summary=revision.change_summary,
        content=revision_content(revision),
        content_digest=(
            revision.content_digest.to_primitive() if revision.content_digest else None
        ),
        created_at=to_naive_utc(revision.created_at),
        created_by=revision.created_by.to_primitive(),
        published_at=to_naive_utc(revision.published_at),
        published_by=revision.published_by.to_primitive() if revision.published_by else None,
    )


def apply_revision_state_to_record(record: TaskRevisionRecord, revision: TaskRevision) -> None:
    """Copy a revision's publication state onto an existing record.

    Content is not copied. A published revision's bytes never change, and this is the code
    path that would otherwise be able to change them.

    Args:
        record: The record to update.
        revision: The revision carrying the new state.
    """
    record.publication_state = str(revision.publication_state)
    record.published_at = to_naive_utc(revision.published_at)
    record.published_by = revision.published_by.to_primitive() if revision.published_by else None
    record.content_digest = (
        revision.content_digest.to_primitive() if revision.content_digest else None
    )


def record_to_revision(record: TaskRevisionRecord) -> TaskRevision:
    """Build a domain revision from a storage record.

    Args:
        record: The stored record.

    Returns:
        The revision.

    Raises:
        ValidationError: If the record is corrupt or violates a domain invariant.
    """
    content = record.content or {}
    if "action" not in content:
        raise ValidationError(
            "A stored revision has no action specification.",
            details={"revision_id": record.revision_id},
        )

    return TaskRevision(
        revision_id=TaskRevisionId(record.revision_id),
        task_id=TaskId(record.task_id),
        revision_number=RevisionNumber(record.revision_number),
        action=ActionSpecification.from_primitive(content["action"]),
        created_at=_require(from_naive_utc(record.created_at), "created_at"),
        created_by=OwnerId(record.created_by),
        schema_version=SchemaVersion.parse(record.schema_version),
        publication_state=PublicationState(record.publication_state),
        controls=ExecutionControls.from_primitive(content.get("controls") or {}),
        deployment=DeploymentSpecification.from_primitive(content.get("deployment") or {}),
        activation_schedule=(
            CronExpression(content["activation_schedule"])
            if content.get("activation_schedule")
            else None
        ),
        change_summary=record.change_summary,
        published_at=from_naive_utc(record.published_at),
        published_by=OwnerId(record.published_by) if record.published_by else None,
        content_digest=ContentDigest(record.content_digest) if record.content_digest else None,
    )


def execution_to_record(execution: Execution) -> ExecutionRecord:
    """Build a storage record from an execution.

    Args:
        execution: The domain execution.

    Returns:
        The record.
    """
    return ExecutionRecord(
        execution_id=execution.execution_id.to_primitive(),
        task_id=execution.task_id.to_primitive(),
        revision_id=execution.revision_id.to_primitive(),
        trigger_source=str(execution.trigger_source),
        state=str(execution.state),
        outcome=str(execution.outcome) if execution.outcome else None,
        reason_code=execution.reason_code.to_primitive() if execution.reason_code else None,
        explanation=execution.explanation,
        requested_at=to_naive_utc(execution.requested_at),
        started_at=to_naive_utc(execution.started_at),
        finished_at=to_naive_utc(execution.finished_at),
        correlation_id=(
            execution.correlation_id.to_primitive() if execution.correlation_id else None
        ),
        idempotency_key=(
            execution.idempotency_key.to_primitive() if execution.idempotency_key else None
        ),
        requested_by=execution.requested_by.to_primitive() if execution.requested_by else None,
        configuration_digest=(
            execution.configuration_digest.to_primitive()
            if execution.configuration_digest
            else None
        ),
    )


def apply_execution_to_record(record: ExecutionRecord, execution: Execution) -> None:
    """Copy an execution's mutable state onto an existing record.

    Identity, task, revision, and request metadata are not copied: they are fixed when the
    execution is created, and rewriting them would let a bug rewrite history.

    Args:
        record: The record to update.
        execution: The execution carrying the new state.
    """
    record.state = str(execution.state)
    record.outcome = str(execution.outcome) if execution.outcome else None
    record.reason_code = execution.reason_code.to_primitive() if execution.reason_code else None
    record.explanation = execution.explanation
    record.started_at = to_naive_utc(execution.started_at)
    record.finished_at = to_naive_utc(execution.finished_at)
    record.configuration_digest = (
        execution.configuration_digest.to_primitive() if execution.configuration_digest else None
    )


def record_to_execution(
    record: ExecutionRecord, attempts: Sequence[ExecutionAttemptRecord] = ()
) -> Execution:
    """Build a domain execution from storage records.

    Args:
        record: The execution record.
        attempts: Its attempt records, in any order; they are sorted here.

    Returns:
        The execution.

    Raises:
        ValidationError: If the records are corrupt or violate a domain invariant.
    """
    return Execution(
        execution_id=ExecutionId(record.execution_id),
        task_id=TaskId(record.task_id),
        revision_id=TaskRevisionId(record.revision_id),
        trigger_source=TriggerSource(record.trigger_source),
        requested_at=_require(from_naive_utc(record.requested_at), "requested_at"),
        state=ExecutionState(record.state),
        outcome=ExecutionOutcome(record.outcome) if record.outcome else None,
        reason_code=ReasonCode(record.reason_code) if record.reason_code else None,
        explanation=record.explanation,
        attempts=tuple(
            record_to_attempt(attempt)
            for attempt in sorted(attempts, key=lambda item: item.attempt_number)
        ),
        started_at=from_naive_utc(record.started_at),
        finished_at=from_naive_utc(record.finished_at),
        correlation_id=CorrelationId(record.correlation_id) if record.correlation_id else None,
        idempotency_key=(
            IdempotencyKey(record.idempotency_key) if record.idempotency_key else None
        ),
        requested_by=OwnerId(record.requested_by) if record.requested_by else None,
        configuration_digest=(
            ContentDigest(record.configuration_digest) if record.configuration_digest else None
        ),
    )


def attempt_to_record(attempt: ExecutionAttempt) -> ExecutionAttemptRecord:
    """Build a storage record from an attempt.

    Args:
        attempt: The domain attempt.

    Returns:
        The record.
    """
    result = attempt.result
    return ExecutionAttemptRecord(
        attempt_id=attempt.attempt_id.to_primitive(),
        execution_id=attempt.execution_id.to_primitive(),
        attempt_number=attempt.attempt_number,
        executor_type=attempt.executor_type,
        started_at=to_naive_utc(attempt.started_at),
        finished_at=to_naive_utc(attempt.finished_at),
        duration_seconds=attempt.duration.to_primitive(),
        termination=str(result.termination) if result else None,
        termination_cause=str(result.termination_cause) if result else None,
        exit_code=result.exit_code if result else None,
        signal_number=result.signal_number if result else None,
        launch_error=result.launch_error if result else None,
        stdout=attempt.stdout,
        stderr=attempt.stderr,
        stdout_bytes=result.stdout_bytes if result else 0,
        stderr_bytes=result.stderr_bytes if result else 0,
        output_truncated=result.output_truncated if result else False,
    )


def apply_attempt_to_record(record: ExecutionAttemptRecord, attempt: ExecutionAttempt) -> None:
    """Copy an attempt's finished state onto an existing record.

    Args:
        record: The record to update.
        attempt: The attempt carrying its result.
    """
    result = attempt.result
    record.finished_at = to_naive_utc(attempt.finished_at)
    record.duration_seconds = attempt.duration.to_primitive()
    record.termination = str(result.termination) if result else None
    record.termination_cause = str(result.termination_cause) if result else None
    record.exit_code = result.exit_code if result else None
    record.signal_number = result.signal_number if result else None
    record.launch_error = result.launch_error if result else None
    record.stdout = attempt.stdout
    record.stderr = attempt.stderr
    record.stdout_bytes = result.stdout_bytes if result else 0
    record.stderr_bytes = result.stderr_bytes if result else 0
    record.output_truncated = result.output_truncated if result else False


def record_to_attempt(record: ExecutionAttemptRecord) -> ExecutionAttempt:
    """Build a domain attempt from a storage record.

    Args:
        record: The stored record.

    Returns:
        The attempt.
    """
    result: ProcessResult | None = None
    if record.termination is not None:
        result = ProcessResult(
            termination=TerminationMode(record.termination),
            duration=Duration(record.duration_seconds),
            exit_code=record.exit_code,
            signal_number=record.signal_number,
            termination_cause=TerminationCause(
                record.termination_cause or TerminationCause.NOT_TERMINATED
            ),
            stdout_bytes=record.stdout_bytes,
            stderr_bytes=record.stderr_bytes,
            output_truncated=record.output_truncated,
            launch_error=record.launch_error,
        )

    return ExecutionAttempt(
        attempt_id=AttemptId(record.attempt_id),
        execution_id=ExecutionId(record.execution_id),
        attempt_number=record.attempt_number,
        started_at=_require(from_naive_utc(record.started_at), "started_at"),
        executor_type=record.executor_type,
        finished_at=from_naive_utc(record.finished_at),
        result=result,
        stdout=record.stdout,
        stderr=record.stderr,
    )
