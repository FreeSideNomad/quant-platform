"""initial (empty) schema — subsequent migrations land in later milestones

Revision ID: 0001
Revises:
Create Date: 2026-04-23 00:00:00.000000

"""
from __future__ import annotations

from alembic import op  # noqa: F401

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Initial migration: creates pgmq extension; no tables yet."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pgmq CASCADE;")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pgmq CASCADE;")
