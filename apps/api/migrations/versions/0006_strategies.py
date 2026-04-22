"""Strategies table — persists SDK register() submissions.

Revision ID: 0006_strategies
Revises: 0005_audit_log
Create Date: 2026-04-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006_strategies"
down_revision = "0005_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategies",
        sa.Column("id", sa.Text, primary_key=True),  # ulid or uuid as text
        sa.Column("family", sa.Text, nullable=False),
        sa.Column(
            "spec", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "registered_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("registered_by", sa.Text, nullable=False),
        sa.Column("spec_hash", sa.Text, nullable=False),
        sa.UniqueConstraint("family", "spec_hash", name="uq_strategies_family_spec_hash"),
    )

    op.create_index("ix_strategies_family", "strategies", ["family"])


def downgrade() -> None:
    op.drop_index("ix_strategies_family", "strategies")
    op.drop_table("strategies")
