"""SQLAlchemy models — storage records, not domain objects.

These classes describe how data is *stored*. They are not the domain, and they must never
be returned from a repository: mappers translate in both directions, so a use case cannot
accidentally depend on a column name or hold a live ORM instance past a session boundary.

Two shape decisions are worth stating, because they will look odd otherwise:

* **Revision content is a JSON document**, not a set of columns. The action specification
  and execution controls are the definition's payload; normalising them would mean a
  migration every time a new executor option appears, and would break the guarantee that a
  published revision's bytes never change. The content digest is stored beside it so
  integrity is checkable without parsing.
* **Timestamps are stored as UTC-naive**, because SQLite cannot hold an offset and would
  otherwise round-trip a timezone-aware value into a lie. The mapper attaches UTC on the
  way out, and a test asserts no naive datetime reaches the domain.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON

TASK_ID_LENGTH = 64
DIGEST_LENGTH = 71  # "sha256:" plus 64 hex characters.


class Base(DeclarativeBase):
    """Declarative base for every TaskControl storage model."""

    type_annotation_map = {dict[str, Any]: JSON}


class TaskRecord(Base):
    """How a task is stored.

    ``storage_version`` is the optimistic-concurrency counter and has nothing to do with
    the domain's revision numbers. It increments on every write to this row; a caller that
    read version 3 and writes expecting 3 fails if someone else already made it 4.
    """

    __tablename__ = "tasks"

    task_id: Mapped[str] = mapped_column(String(TASK_ID_LENGTH), primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    owner_id: Mapped[str] = mapped_column(String(TASK_ID_LENGTH), nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False)
    active_revision_id: Mapped[str | None] = mapped_column(String(TASK_ID_LENGTH), nullable=True)
    labels: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    created_by: Mapped[str] = mapped_column(String(TASK_ID_LENGTH), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(TASK_ID_LENGTH), nullable=True)

    storage_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        # A slug appears in URLs and generated artefacts, so it must identify exactly one
        # task. Enforced here as well as in the domain because the database can guarantee
        # it across concurrent writers and the domain cannot.
        UniqueConstraint("slug", name="uq_tasks_slug"),
        # The domain forbids an active task with no revision. Stating it again as a
        # constraint means no code path — including a future migration — can create one.
        CheckConstraint(
            "lifecycle_state != 'active' OR active_revision_id IS NOT NULL",
            name="ck_tasks_active_requires_revision",
        ),
        Index("ix_tasks_lifecycle_state", "lifecycle_state"),
        Index("ix_tasks_owner_id", "owner_id"),
    )


class TaskRevisionRecord(Base):
    """How a task revision is stored.

    There is no ``storage_version``: a published revision's content is immutable, so the
    only writes are publication-state transitions, and those are guarded by the domain.
    """

    __tablename__ = "task_revisions"

    revision_id: Mapped[str] = mapped_column(String(TASK_ID_LENGTH), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String(TASK_ID_LENGTH),
        # RESTRICT, not CASCADE: deleting a task must never silently destroy the revisions
        # that past executions refer to. Retirement and archival are the supported paths.
        ForeignKey("tasks.task_id", ondelete="RESTRICT"),
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    publication_state: Mapped[str] = mapped_column(String(32), nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")

    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_digest: Mapped[str | None] = mapped_column(String(DIGEST_LENGTH), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    created_by: Mapped[str] = mapped_column(String(TASK_ID_LENGTH), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(TASK_ID_LENGTH), nullable=True)

    __table_args__ = (
        # Revision numbers never repeat within a task. The domain allocates them; the
        # database makes a concurrent double-allocation impossible.
        UniqueConstraint("task_id", "revision_number", name="uq_revisions_task_number"),
        # A frozen revision must carry a digest. Without this a corrupted write could
        # produce an unverifiable published revision.
        CheckConstraint(
            "publication_state = 'draft' OR content_digest IS NOT NULL",
            name="ck_revisions_frozen_requires_digest",
        ),
        CheckConstraint("revision_number >= 1", name="ck_revisions_number_positive"),
        Index("ix_revisions_task_id", "task_id"),
        Index("ix_revisions_publication_state", "publication_state"),
    )


class ExecutionRecord(Base):
    """How an execution is stored.

    Rows exist for executions that never ran a process. A skipped or blocked execution is
    a first-class record with an outcome and a reason code — that is the point.

    ``outcome`` is nullable because an in-flight execution has none. A ``finished`` row with
    a null outcome would be an execution nobody can explain, so a constraint forbids it.
    """

    __tablename__ = "executions"

    execution_id: Mapped[str] = mapped_column(String(TASK_ID_LENGTH), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String(TASK_ID_LENGTH),
        ForeignKey("tasks.task_id", ondelete="RESTRICT"),
        nullable=False,
    )
    revision_id: Mapped[str] = mapped_column(
        String(TASK_ID_LENGTH),
        ForeignKey("task_revisions.revision_id", ondelete="RESTRICT"),
        nullable=False,
    )
    trigger_source: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")

    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    requested_by: Mapped[str | None] = mapped_column(String(TASK_ID_LENGTH), nullable=True)
    configuration_digest: Mapped[str | None] = mapped_column(String(DIGEST_LENGTH), nullable=True)

    __table_args__ = (
        # An execution recorded as finished with no outcome is one nobody can explain.
        CheckConstraint(
            "state != 'finished' OR outcome IS NOT NULL",
            name="ck_executions_finished_requires_outcome",
        ),
        # A duplicate trigger delivery must not produce a duplicate execution.
        UniqueConstraint("task_id", "idempotency_key", name="uq_executions_idempotency"),
        Index("ix_executions_task_id", "task_id"),
        Index("ix_executions_state", "state"),
        Index("ix_executions_outcome", "outcome"),
        # History is read newest-first per task, which is the only listing the API offers.
        Index("ix_executions_task_requested", "task_id", "requested_at"),
    )


class ExecutionAttemptRecord(Base):
    """How one attempt within an execution is stored.

    stdout and stderr are separate columns and stay separate. Interleaving them would lose
    the distinction between a program's result and its diagnostics.
    """

    __tablename__ = "execution_attempts"

    attempt_id: Mapped[str] = mapped_column(String(TASK_ID_LENGTH), primary_key=True)
    execution_id: Mapped[str] = mapped_column(
        String(TASK_ID_LENGTH),
        # CASCADE here, unlike elsewhere: an attempt has no meaning without its execution,
        # and executions are never deleted while a task references them.
        ForeignKey("executions.execution_id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    executor_type: Mapped[str] = mapped_column(String(32), nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    termination: Mapped[str | None] = mapped_column(String(32), nullable=True)
    termination_cause: Mapped[str | None] = mapped_column(String(32), nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signal_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    launch_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    stdout: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stderr: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stdout_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stderr_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("execution_id", "attempt_number", name="uq_attempts_execution_number"),
        CheckConstraint("attempt_number >= 1", name="ck_attempts_number_positive"),
        Index("ix_attempts_execution_id", "execution_id"),
    )


class ClaimRecord(Base):
    """How a durable claim is stored (ADR 0023).

    One row per subject, and the row is **never deleted** — releasing sets the expiry to
    now rather than removing anything. That is what keeps the fencing token monotonic: a
    deleted row would restart the count, and a stalled owner holding token 7 would find
    the subject back at token 1 and conclude it was still current.

    Exclusivity is the primary key doing its job. Two processes racing to claim the same
    subject cannot both insert it, and taking over a lapsed claim is a conditional update
    that only one of them can win.
    """

    __tablename__ = "claims"

    subject: Mapped[str] = mapped_column(String(200), primary_key=True)
    owner: Mapped[str] = mapped_column(String(200), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    fencing_token: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        CheckConstraint("fencing_token >= 1", name="ck_claims_token_positive"),
        Index("ix_claims_expires_at", "expires_at"),
    )
