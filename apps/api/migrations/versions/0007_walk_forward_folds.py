"""Walk-forward folds table — stores per-fold train/test metrics for walk-forward validation.

Revision ID: 0007_walk_forward_folds
Revises: 0006_strategies
Create Date: 2026-04-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0007_walk_forward_folds"
down_revision = "0006_strategies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "walk_forward_folds",
        sa.Column(
            "id",
            sa.BigInteger,
            sa.Identity(always=True),
            primary_key=True,
        ),
        sa.Column("training_run_id", sa.Text, nullable=False),
        sa.Column("fold_index", sa.Integer, nullable=False),
        sa.Column("train_start", sa.Date, nullable=False),
        sa.Column("train_end", sa.Date, nullable=False),
        sa.Column("test_start", sa.Date, nullable=False),
        sa.Column("test_end", sa.Date, nullable=False),
        sa.Column("in_sample_ic", sa.Float, nullable=True),
        sa.Column("out_of_sample_ic", sa.Float, nullable=True),
        sa.Column("out_of_sample_sharpe", sa.Float, nullable=True),
        sa.Column(
            "metrics",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "training_run_id", "fold_index", name="uq_wff_run_fold"
        ),
    )

    op.create_index("ix_wff_run", "walk_forward_folds", ["training_run_id"])


def downgrade() -> None:
    op.drop_index("ix_wff_run", "walk_forward_folds")
    op.drop_table("walk_forward_folds")
