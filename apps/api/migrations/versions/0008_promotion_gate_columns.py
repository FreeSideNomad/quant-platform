"""Add gate-evaluation columns to model_versions.

Revision ID: 0008_promotion_gate_columns
Revises: 0007_walk_forward_folds
Create Date: 2026-04-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_promotion_gate_columns"
down_revision = "0007_walk_forward_folds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("model_versions", sa.Column("pbo", sa.Float, nullable=True))
    op.add_column("model_versions", sa.Column("dsr_probability", sa.Float, nullable=True))
    op.add_column(
        "model_versions",
        sa.Column("walk_forward_fold_count", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("model_versions", "walk_forward_fold_count")
    op.drop_column("model_versions", "dsr_probability")
    op.drop_column("model_versions", "pbo")
