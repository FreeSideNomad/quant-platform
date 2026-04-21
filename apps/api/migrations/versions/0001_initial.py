"""initial schema — events, proj_ui_pings, processed_events, PGMQ queues

Revision ID: 0001
Revises:
Create Date: 2026-04-21 00:00:00
"""

from __future__ import annotations

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PGMQ extension must already be available on the server. Creating if missing.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgmq")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id           uuid        PRIMARY KEY,
            aggregate_type text      NOT NULL,
            aggregate_id uuid        NOT NULL,
            event_type   text        NOT NULL,
            payload      jsonb       NOT NULL,
            occurred_at  timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS events_aggregate_idx "
        "ON events (aggregate_type, aggregate_id, occurred_at)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS proj_ui_pings (
            event_id     uuid        PRIMARY KEY,
            message      text        NOT NULL,
            projected_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS processed_events (
            projector_name text NOT NULL,
            event_id       uuid NOT NULL,
            processed_at   timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (projector_name, event_id)
        )
        """
    )

    # Create the initial set of PGMQ queues. Safe to call multiple times.
    op.execute(
        "SELECT pgmq.create('proj_ui') WHERE NOT EXISTS "
        "(SELECT 1 FROM pgmq.list_queues() WHERE queue_name = 'proj_ui')"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS processed_events")
    op.execute("DROP TABLE IF EXISTS proj_ui_pings")
    op.execute("DROP TABLE IF EXISTS events")
    op.execute("SELECT pgmq.drop_queue('proj_ui')")
