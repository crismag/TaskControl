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
