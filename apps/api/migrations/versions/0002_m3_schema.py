"""M3 schema: strategies, runs, events, datasets, dataset_versions, lineage_reads

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-24 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
        sa.UniqueConstraint("dataset_id", "version_tag", name="uq_dataset_versions_dataset_id_version_tag"),
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

    # Seed the bundled demo dataset. Storage URI points at MinIO; the actual
    # upload is done by the minio-init one-shot service on `pq up`.
    #
    # content_hash is the xxh64 of apps/api/data/spy_daily.parquet as generated
    # by scripts/bundle_spy_data.py. If you regenerate the parquet, update the
    # hex literal below. The test_bundled_dataset.py test enforces this stays
    # in sync with the actual file bytes.
    op.execute(
        """
        INSERT INTO datasets (name, description, schema_json, content_hash_scheme)
        VALUES (
          'ohlcv-spy-daily-synthetic',
          'Synthetic ~10y daily OHLCV with GARCH-like vol clustering (seed=20260424). '
          'Generated by scripts/bundle_spy_data.py. NOT real SPY historical data — '
          'labelled spy_daily for developer familiarity only. Users register real data with pq data register (v2).',
          '{"columns": ["date", "open", "high", "low", "close", "adj_close", "volume"]}'::jsonb,
          'xxh64'
        )
        ON CONFLICT (name) DO NOTHING;
        """
    )
    op.execute(
        r"""
        INSERT INTO dataset_versions (dataset_id, version_tag, storage_uri, content_hash, schema_json, effective_at)
        SELECT d.id,
               'v1',
               's3://qp-artifacts/datasets/ohlcv-spy-daily-synthetic/v1/spy_daily.parquet',
               '\x76b70beff25612da'::bytea,
               '{}'::jsonb,
               NOW()
        FROM datasets d WHERE d.name = 'ohlcv-spy-daily-synthetic'
        ON CONFLICT (dataset_id, version_tag) DO NOTHING;
        """
    )


def downgrade() -> None:
    # Delete seed rows before dropping tables (FK order)
    op.execute("DELETE FROM dataset_versions WHERE version_tag = 'v1' AND dataset_id IN (SELECT id FROM datasets WHERE name = 'ohlcv-spy-daily-synthetic');")
    op.execute("DELETE FROM datasets WHERE name = 'ohlcv-spy-daily-synthetic';")
    # Drop in reverse FK order
    op.drop_table("lineage_reads")
    op.drop_table("dataset_versions")
    op.drop_table("datasets")
    op.drop_table("events")
    op.drop_table("runs")
    op.drop_table("strategies")
