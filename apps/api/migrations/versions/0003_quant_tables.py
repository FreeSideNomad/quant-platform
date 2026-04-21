"""quant: instruments, daily_prices_silver, features_gold, models, training_runs, inference_log

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-21 02:00:00
"""

from __future__ import annotations

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Instruments universe (seed with a handful of synthetic names for demo)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS instruments (
            instrument   text PRIMARY KEY,
            market       text NOT NULL,
            listed_at    date NOT NULL,
            delisted_at  date,
            display_name text NOT NULL
        )
        """
    )

    # Silver: daily OHLCV. _knowable_at is the platform ingest time — point-in-time
    # correctness uses this, not the trade date.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_prices_silver (
            instrument    text         NOT NULL REFERENCES instruments(instrument),
            trade_date    date         NOT NULL,
            open          double precision NOT NULL,
            high          double precision NOT NULL,
            low           double precision NOT NULL,
            close         double precision NOT NULL,
            volume        double precision NOT NULL,
            adj_close     double precision NOT NULL,
            knowable_at   timestamptz  NOT NULL DEFAULT now(),
            source_uri    text,
            PRIMARY KEY (instrument, trade_date)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS daily_prices_silver_date_idx "
        "ON daily_prices_silver (trade_date)"
    )

    # Gold: features materialised per (instrument, trade_date) with a forward target.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS features_gold (
            instrument    text NOT NULL,
            trade_date    date NOT NULL,
            mom_5         double precision,
            mom_20        double precision,
            vol_20        double precision,
            return_mean_20 double precision,
            hl_range      double precision,
            vol_ratio_20  double precision,
            target_fwd_1d double precision,
            knowable_at   timestamptz  NOT NULL DEFAULT now(),
            PRIMARY KEY (instrument, trade_date)
        )
        """
    )

    # Models registry (thin wrapper over MLflow — MLflow holds artefacts and metrics,
    # this table records domain lifecycle state and is the source of truth for the UI).
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS models (
            id             text PRIMARY KEY,
            name           text NOT NULL,
            description    text,
            algorithm      text NOT NULL,
            owner_email    text,
            created_at     timestamptz NOT NULL DEFAULT now(),
            updated_at     timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS training_runs (
            id                 text PRIMARY KEY,
            model_id           text NOT NULL REFERENCES models(id) ON DELETE CASCADE,
            mlflow_run_id      text,
            status             text NOT NULL
                CHECK (status IN ('submitted','running','completed','failed')),
            compute_profile    text NOT NULL
                CHECK (compute_profile IN ('local-cpu','local-gpu','cloud-cpu','cloud-gpu')),
            as_of              date NOT NULL,
            train_start        date NOT NULL,
            train_end          date NOT NULL,
            instruments        text[] NOT NULL,
            hyperparameters    jsonb NOT NULL DEFAULT '{}'::jsonb,
            metrics            jsonb NOT NULL DEFAULT '{}'::jsonb,
            artefact_uri       text,
            model_version      text,
            started_at         timestamptz NOT NULL DEFAULT now(),
            completed_at       timestamptz,
            submitted_by       text,
            error              text
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS training_runs_model_idx ON training_runs (model_id, started_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS model_versions (
            id              text PRIMARY KEY,
            model_id        text NOT NULL REFERENCES models(id) ON DELETE CASCADE,
            training_run_id text NOT NULL REFERENCES training_runs(id) ON DELETE CASCADE,
            version         text NOT NULL,
            stage           text NOT NULL
                CHECK (stage IN ('draft','validated','production','archived')),
            mlflow_model_version text,
            created_at      timestamptz NOT NULL DEFAULT now(),
            promoted_at     timestamptz,
            metrics         jsonb NOT NULL DEFAULT '{}'::jsonb
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inference_log (
            id               text PRIMARY KEY,
            model_id         text NOT NULL REFERENCES models(id) ON DELETE CASCADE,
            model_version    text NOT NULL,
            instrument       text NOT NULL,
            as_of_date       date NOT NULL,
            feature_hash     text NOT NULL,
            prediction       double precision NOT NULL,
            latency_ms       integer NOT NULL,
            requested_by     text,
            requested_at     timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS inference_log_model_idx "
        "ON inference_log (model_id, requested_at DESC)"
    )

    # Create the PGMQ queue used by the training worker
    op.execute(
        "SELECT pgmq.create('training') WHERE NOT EXISTS "
        "(SELECT 1 FROM pgmq.list_queues() WHERE queue_name = 'training')"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS inference_log")
    op.execute("DROP TABLE IF EXISTS model_versions")
    op.execute("DROP TABLE IF EXISTS training_runs")
    op.execute("DROP TABLE IF EXISTS models")
    op.execute("DROP TABLE IF EXISTS features_gold")
    op.execute("DROP TABLE IF EXISTS daily_prices_silver")
    op.execute("DROP TABLE IF EXISTS instruments")
    op.execute("SELECT pgmq.drop_queue('training')")
