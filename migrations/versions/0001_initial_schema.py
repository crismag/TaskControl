"""Initial schema: tasks and task revisions.

Revision ID: 0001
Revises:
Created: 2026-07-27

Downgrade drops both tables and therefore destroys every task definition and revision.
That is acceptable only because this is the first migration — there is no earlier state to
return to. Later migrations that lose data must stage the change and document recovery,
per the database standards.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TASK_ID_LENGTH = 64
DIGEST_LENGTH = 71


def upgrade() -> None:
    """Create the tasks and task_revisions tables."""
    op.create_table(
        "tasks",
        sa.Column("task_id", sa.String(TASK_ID_LENGTH), primary_key=True),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("owner_id", sa.String(TASK_ID_LENGTH), nullable=False),
        sa.Column("lifecycle_state", sa.String(32), nullable=False),
        sa.Column("active_revision_id", sa.String(TASK_ID_LENGTH), nullable=True),
        sa.Column("labels", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("created_by", sa.String(TASK_ID_LENGTH), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("updated_by", sa.String(TASK_ID_LENGTH), nullable=True),
        sa.Column("storage_version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("slug", name="uq_tasks_slug"),
        sa.CheckConstraint(
            "lifecycle_state != 'active' OR active_revision_id IS NOT NULL",
            name="ck_tasks_active_requires_revision",
        ),
    )
    op.create_index("ix_tasks_lifecycle_state", "tasks", ["lifecycle_state"])
    op.create_index("ix_tasks_owner_id", "tasks", ["owner_id"])

    op.create_table(
        "task_revisions",
        sa.Column("revision_id", sa.String(TASK_ID_LENGTH), primary_key=True),
        sa.Column("task_id", sa.String(TASK_ID_LENGTH), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("publication_state", sa.String(32), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("content_digest", sa.String(DIGEST_LENGTH), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("created_by", sa.String(TASK_ID_LENGTH), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("published_by", sa.String(TASK_ID_LENGTH), nullable=True),
        # RESTRICT, not CASCADE: deleting a task must never silently destroy the revisions
        # that past executions refer to.
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name="fk_revisions_task_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("task_id", "revision_number", name="uq_revisions_task_number"),
        sa.CheckConstraint(
            "publication_state = 'draft' OR content_digest IS NOT NULL",
            name="ck_revisions_frozen_requires_digest",
        ),
        sa.CheckConstraint("revision_number >= 1", name="ck_revisions_number_positive"),
    )
    op.create_index("ix_revisions_task_id", "task_revisions", ["task_id"])
    op.create_index("ix_revisions_publication_state", "task_revisions", ["publication_state"])


def downgrade() -> None:
    """Drop both tables.

    Destroys every task definition and revision. Safe only because there is no earlier
    schema to return to.
    """
    op.drop_index("ix_revisions_publication_state", table_name="task_revisions")
    op.drop_index("ix_revisions_task_id", table_name="task_revisions")
    op.drop_table("task_revisions")

    op.drop_index("ix_tasks_owner_id", table_name="tasks")
    op.drop_index("ix_tasks_lifecycle_state", table_name="tasks")
    op.drop_table("tasks")
