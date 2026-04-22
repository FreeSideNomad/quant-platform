"""Hash-chained audit_log table.

Revision ID: 0005_audit_log
Revises: 0004
Create Date: 2026-04-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0005_audit_log"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column(
            "occurred_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("actor", sa.Text, nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("aggregate_type", sa.Text, nullable=False),
        sa.Column("aggregate_id", sa.Text, nullable=False),
        sa.Column(
            "payload", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("prev_hash", sa.Text, nullable=True),
        sa.Column("row_hash", sa.Text, nullable=False),
    )

    op.create_index(
        "ix_audit_log_aggregate", "audit_log", ["aggregate_type", "aggregate_id"]
    )
    op.create_index("ix_audit_log_occurred_at", "audit_log", ["occurred_at"])
    op.create_index("ix_audit_log_event_type", "audit_log", ["event_type"])

    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_log_block_mutations()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only (operation: %)', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_block_update
            BEFORE UPDATE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION audit_log_block_mutations();
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_block_delete
            BEFORE DELETE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION audit_log_block_mutations();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_block_delete ON audit_log;")
    op.execute("DROP TRIGGER IF EXISTS audit_log_block_update ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS audit_log_block_mutations();")
    op.drop_table("audit_log")
