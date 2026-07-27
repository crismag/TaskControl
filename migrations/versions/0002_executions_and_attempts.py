"""Executions and attempts.

Revision ID: 0002
Revises: 0001
Created: 2026-07-27

Adds the execution history. Rows exist for executions that never ran a process — a skipped
or blocked execution is a first-class record with an outcome and a reason code.

Downgrade drops both tables and therefore destroys all execution history. Task definitions
and revisions are untouched, so a downgrade loses observability rather than intent. Take a
backup first: history cannot be reconstructed.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ID_LENGTH = 64
DIGEST_LENGTH = 71


def upgrade() -> None:
    """Create the executions and execution_attempts tables."""
    op.create_table(
        "executions",
        sa.Column("execution_id", sa.String(ID_LENGTH), primary_key=True),
        sa.Column("task_id", sa.String(ID_LENGTH), nullable=False),
        sa.Column("revision_id", sa.String(ID_LENGTH), nullable=False),
        sa.Column("trigger_source", sa.String(32), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=True),
        sa.Column("reason_code", sa.String(100), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=False, server_default=""),
        sa.Column("requested_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("requested_by", sa.String(ID_LENGTH), nullable=True),
        sa.Column("configuration_digest", sa.String(DIGEST_LENGTH), nullable=True),
        # RESTRICT on both: an execution is the evidence that a revision ran, and deleting
        # the definition must never destroy the evidence.
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.task_id"], name="fk_executions_task_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["task_revisions.revision_id"],
            name="fk_executions_revision_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "state != 'finished' OR outcome IS NOT NULL",
            name="ck_executions_finished_requires_outcome",
        ),
        sa.UniqueConstraint("task_id", "idempotency_key", name="uq_executions_idempotency"),
    )
    op.create_index("ix_executions_task_id", "executions", ["task_id"])
    op.create_index("ix_executions_state", "executions", ["state"])
    op.create_index("ix_executions_outcome", "executions", ["outcome"])
    op.create_index("ix_executions_task_requested", "executions", ["task_id", "requested_at"])

    op.create_table(
        "execution_attempts",
        sa.Column("attempt_id", sa.String(ID_LENGTH), primary_key=True),
        sa.Column("execution_id", sa.String(ID_LENGTH), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("executor_type", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("termination", sa.String(32), nullable=True),
        sa.Column("termination_cause", sa.String(32), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("signal_number", sa.Integer(), nullable=True),
        sa.Column("launch_error", sa.Text(), nullable=True),
        sa.Column("stdout", sa.Text(), nullable=False, server_default=""),
        sa.Column("stderr", sa.Text(), nullable=False, server_default=""),
        sa.Column("stdout_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stderr_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_truncated", sa.Boolean(), nullable=False, server_default=sa.false()),
        # CASCADE, unlike elsewhere: an attempt has no meaning without its execution, and
        # executions are themselves protected by RESTRICT from their task and revision.
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.execution_id"],
            name="fk_attempts_execution_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("execution_id", "attempt_number", name="uq_attempts_execution_number"),
        sa.CheckConstraint("attempt_number >= 1", name="ck_attempts_number_positive"),
    )
    op.create_index("ix_attempts_execution_id", "execution_attempts", ["execution_id"])


def downgrade() -> None:
    """Drop the execution history.

    Destroys every execution and attempt record. Task definitions survive, so this loses
    observability rather than intent — but history cannot be reconstructed, so back up
    first.
    """
    op.drop_index("ix_attempts_execution_id", table_name="execution_attempts")
    op.drop_table("execution_attempts")

    op.drop_index("ix_executions_task_requested", table_name="executions")
    op.drop_index("ix_executions_outcome", table_name="executions")
    op.drop_index("ix_executions_state", table_name="executions")
    op.drop_index("ix_executions_task_id", table_name="executions")
    op.drop_table("executions")
