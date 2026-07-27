"""Durable claims.

Revision ID: 0003
Revises: 0002
Created: 2026-07-27

Adds the one claim table that serves both overlap protection and, later, queue claiming
(ADR 0023). Until this exists, cron-activated work has no overlap protection at all
between processes — not weaker protection, none — so this migration is what makes the
product's overlap promise true rather than nominal.

Rows are never deleted by the application: releasing a claim lapses it by setting the
expiry to now. That keeps the fencing token monotonic per subject.

Downgrade drops the table. Any claim held at that moment is lost, so overlapping work
becomes possible immediately. Stop activation before downgrading.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUBJECT_LENGTH = 200
OWNER_LENGTH = 200


def upgrade() -> None:
    """Create the claims table."""
    op.create_table(
        "claims",
        sa.Column("subject", sa.String(SUBJECT_LENGTH), primary_key=True),
        sa.Column("owner", sa.String(OWNER_LENGTH), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("fencing_token", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint("fencing_token >= 1", name="ck_claims_token_positive"),
    )
    # Expiry is what every acquisition and every diagnostic filters on.
    op.create_index("ix_claims_expires_at", "claims", ["expires_at"])


def downgrade() -> None:
    """Drop the claims table, and with it every held claim."""
    op.drop_index("ix_claims_expires_at", table_name="claims")
    op.drop_table("claims")
