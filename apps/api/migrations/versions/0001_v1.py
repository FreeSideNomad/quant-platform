"""v1 schema: pgmq + strategies + runs + events + datasets + dataset_versions + lineage_reads.

This is the consolidated initial migration. Earlier development carried
two separate migrations (0001_initial creating only the pgmq extension,
0002_m3_schema adding the M3 tables); they were merged into this single
v1 migration before any external user state existed. Future schema
changes land as new revisions on top of this one.

The bundled dataset's `content_hash` and `schema_json` come from a
sidecar JSON file (`aapl_daily.meta.json`) written by the same fetch
that produced the parquet — single coherent artifact, no drift
possible. The migration container only needs stdlib + alembic to read
it, no polars / xxhash bloat. Refresh both files via
`scripts/refresh_aapl_data.py`; nothing in this migration needs editing.

Revision ID: 0001_v1
Revises:
Create Date: 2026-04-25 00:00:00.000000
"""
from __future__ import annotations

import json
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_v1"
down_revision = None
branch_labels = None
depends_on = None

# Path to the bundled dataset metadata sidecar (written alongside the
# parquet by scripts/refresh_aapl_data.py). The api / migrations
# container has only stdlib + alembic — reading JSON keeps the
# container slim. parents: [0]=versions/ [1]=migrations/ [2]=api/
_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_BUNDLED_META = _DATA_DIR / "aapl_daily.meta.json"


def upgrade() -> None:
    # --- extensions ---
    op.execute("CREATE EXTENSION IF NOT EXISTS pgmq CASCADE;")

    # --- strategies ---
    op.create_table(
        "strategies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("owner", sa.Text, nullable=True),
        sa.Column(
            "thresholds",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("git_sha", sa.Text, nullable=True),
        sa.Column("uv_lock_hash", sa.Text, nullable=True),
        sa.Column("entry_point", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # --- runs ---
    op.create_table(
        "runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "strategy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("strategies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("as_of", sa.Date, nullable=True),
        sa.Column(
            "status",
            sa.Text,
            nullable=False,
            server_default=sa.text("'running'"),
        ),
        sa.Column("git_sha", sa.Text, nullable=True),
        sa.Column("uv_lock_hash", sa.Text, nullable=True),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.execute(
        "ALTER TABLE runs ADD CONSTRAINT runs_status_check "
        "CHECK (status IN ('running', 'succeeded', 'failed'))"
    )
    op.create_index(
        "ix_runs_strategy_id_started_at",
        "runs",
        ["strategy_id", sa.text("started_at DESC")],
    )

    # --- events (hash-chained audit log) ---
    op.create_table(
        "events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("prev_hash", postgresql.BYTEA, nullable=False),
        sa.Column("this_hash", postgresql.BYTEA, nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.execute(
        "CREATE INDEX ix_events_run_id_created_at "
        "ON events (run_id, created_at) "
        "WHERE run_id IS NOT NULL"
    )
    op.create_index(
        "ix_events_event_type_created_at",
        "events",
        ["event_type", "created_at"],
    )

    # --- datasets ---
    op.create_table(
        "datasets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "schema_json",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "content_hash_scheme",
            sa.Text,
            nullable=False,
            server_default=sa.text("'xxh64'"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.execute(
        "ALTER TABLE datasets ADD CONSTRAINT datasets_content_hash_scheme_check "
        "CHECK (content_hash_scheme IN ('xxh64', 'sha256'))"
    )

    # --- dataset_versions ---
    op.create_table(
        "dataset_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "dataset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("datasets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version_tag", sa.Text, nullable=False),
        sa.Column("storage_uri", sa.Text, nullable=False),
        sa.Column("content_hash", postgresql.BYTEA, nullable=False),
        sa.Column(
            "schema_json",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "effective_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint(
            "dataset_id", "version_tag", name="uq_dataset_versions_dataset_id_version_tag"
        ),
    )

    # --- lineage_reads ---
    op.create_table(
        "lineage_reads",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dataset_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dataset_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("as_of", sa.Date, nullable=True),
        sa.Column(
            "filter_predicates",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("content_hash", postgresql.BYTEA, nullable=False),
        sa.Column(
            "read_timestamp",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("rows_returned", sa.BigInteger, nullable=False),
    )
    op.create_index(
        "ix_lineage_reads_run_id_read_timestamp",
        "lineage_reads",
        ["run_id", "read_timestamp"],
    )
    op.create_index(
        "ix_lineage_reads_dataset_version_id",
        "lineage_reads",
        ["dataset_version_id"],
    )

    # Seed the bundled demo dataset. Storage URI points at MinIO; the
    # actual upload is done by the minio-init one-shot service on `pq up`.
    #
    # content_hash + schema come from the sidecar JSON written by the
    # refresh script — both files ship together; drift is caught by
    # apps/api/tests/test_bundled_dataset.py (which runs in a test env
    # that has polars + xxhash to verify against the parquet bytes).
    if not _BUNDLED_META.is_file():
        raise FileNotFoundError(
            f"Bundled dataset metadata not found at {_BUNDLED_META}. "
            f"Refresh via `uv run python scripts/refresh_aapl_data.py` (maintainer)."
        )
    meta = json.loads(_BUNDLED_META.read_text())
    content_hash_hex = meta["content_hash_hex"]
    schema_json = json.dumps(meta["schema"])

    op.execute(
        sa.text(
            """
            INSERT INTO datasets (name, description, schema_json, content_hash_scheme)
            VALUES (
              'ohlcv-aapl-daily',
              'Real AAPL daily OHLCV historical bars. Source: '
              'https://www.kaggle.com/datasets/jacksoncrow/stock-market-dataset '
              '(CC0 Public Domain). See apps/api/data/PROVENANCE.md for fetch '
              'date and date range. Refresh via scripts/refresh_aapl_data.py.',
              CAST(:schema_json AS jsonb),
              'xxh64'
            )
            ON CONFLICT (name) DO NOTHING;
            """
        ).bindparams(schema_json=schema_json)
    )
    op.execute(
        sa.text(
            """
            INSERT INTO dataset_versions (dataset_id, version_tag, storage_uri, content_hash, schema_json, effective_at)
            SELECT d.id,
                   'v1',
                   's3://qp-artifacts/datasets/ohlcv-aapl-daily/v1/aapl_daily.parquet',
                   decode(:content_hash_hex, 'hex'),
                   CAST(:schema_json AS jsonb),
                   NOW()
            FROM datasets d WHERE d.name = 'ohlcv-aapl-daily'
            ON CONFLICT (dataset_id, version_tag) DO NOTHING;
            """
        ).bindparams(content_hash_hex=content_hash_hex, schema_json=schema_json)
    )


def downgrade() -> None:
    # Delete seed rows before dropping tables (FK order)
    op.execute(
        "DELETE FROM dataset_versions WHERE version_tag = 'v1' AND dataset_id IN "
        "(SELECT id FROM datasets WHERE name = 'ohlcv-aapl-daily');"
    )
    op.execute("DELETE FROM datasets WHERE name = 'ohlcv-aapl-daily';")
    # Drop in reverse FK order
    op.drop_table("lineage_reads")
    op.drop_table("dataset_versions")
    op.drop_table("datasets")
    op.drop_table("events")
    op.drop_table("runs")
    op.drop_table("strategies")
    op.execute("DROP EXTENSION IF EXISTS pgmq CASCADE;")
