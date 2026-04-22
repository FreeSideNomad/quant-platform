"""Reproducible demo seed.

Provisions a tenant from a clean state to a state where the demo
narrative (PRD §3.3) runs end-to-end:
  - Synthetic universe + Alpha features in gold layer (Dagster)
  - Walk-forward training with per-fold rows persisted (Dagster)
  - One registered strategy + StrategyRegistered audit event
  - One model version promoted to production with PBO/DSR
  - One inference logged

The data + training stages run via `dagster asset materialize -m
app.dagster_defs --job demo_full_lineage`, so the Dagster UI shows
the full lineage for the demo. The strategy/promotion/inference
steps that are not (yet) Dagster assets run after the job completes.

Idempotent: rerunning is safe (TRUNCATEs the relevant tables first).
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
import uuid
from datetime import date

import numpy as np
from sqlalchemy import text

from app.audit.log import append_audit_event
from app.infra.db import session_scope
from app.quant.validation.dsr import deflated_sharpe
from app.quant.validation.pbo import pbo


async def _truncate_state() -> None:
    async with session_scope() as session:
        await session.execute(
            text(
                """TRUNCATE TABLE audit_log, walk_forward_folds, inference_log,
                              model_versions, training_runs, strategies,
                              features_gold, daily_prices_silver
                   RESTART IDENTITY CASCADE"""
            )
        )
        await session.commit()


def _run_dagster_demo_job(training_run_id: str) -> None:
    """Materialise bronze -> silver -> gold -> walk_forward_fold_results via Dagster.

    Uses `dagster asset materialize --config-json` (the proven pattern from Task 3.4).
    DAGSTER_HOME is pointed at a tempdir to bypass any dagster.yaml Postgres requirement.
    The in_process executor is requested to avoid a separate daemon requirement.
    """
    dagster_home = tempfile.mkdtemp(prefix="dagster_home_demo_")

    config = json.dumps(
        {
            "ops": {
                "bronze_synthetic_universe": {
                    "config": {
                        "start": "2018-01-01",
                        "end": "2024-12-31",
                        "seed": 42,
                    }
                },
                "walk_forward_fold_results": {
                    "config": {
                        "training_run_id": training_run_id,
                        "step": "quarter",
                        "train_window": "3y",
                        "test_window": "1q",
                        "min_folds": 4,
                        "as_of": "2024-12-31",
                    }
                },
            },
            "execution": {"config": {"in_process": {}}},
        }
    )

    env = {
        **os.environ,
        "DAGSTER_HOME": dagster_home,
    }

    result = subprocess.run(
        [
            "uv",
            "run",
            "dagster",
            "asset",
            "materialize",
            "-m",
            "app.dagster_defs",
            "--select",
            "bronze_synthetic_universe,silver_pit_prices,gold_alpha_features,walk_forward_fold_results",
            "--config-json",
            config,
        ],
        capture_output=True,
        text=True,
        timeout=900,
        cwd="/Users/igormusic/code/deployment/quant-platform/apps/api",
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"dagster asset materialize failed:\n--- stderr ---\n{result.stderr}\n"
            f"--- stdout ---\n{result.stdout}"
        )


async def run_demo_seed() -> dict:
    """Seed the demo state. Returns a dict of inserted ids for verification."""
    await _truncate_state()

    strategy_id = "demo-strategy-1"
    training_run_id = "demo-trun-1"

    async with session_scope() as session:
        await session.execute(
            text(
                """INSERT INTO strategies (id, family, spec, registered_by, spec_hash)
                   VALUES (:id, 'qlib-lgbm-demo', '{"demo": true}'::jsonb,
                           'demo@example.com', 'demo-hash')"""
            ),
            {"id": strategy_id},
        )
        await append_audit_event(
            session,
            actor="demo@example.com",
            event_type="StrategyRegistered",
            aggregate_type="Strategy",
            aggregate_id=strategy_id,
            payload={"family": "qlib-lgbm-demo"},
        )
        # Insert training_run with all NOT NULL columns satisfied
        await session.execute(
            text(
                """INSERT INTO training_runs
                       (id, model_id, status, compute_profile, as_of,
                        train_start, train_end, instruments)
                   VALUES (:id, 'qlib-lgbm', 'running', 'local-cpu',
                           '2024-12-31', '2018-01-01', '2024-12-31', '{}')"""
            ),
            {"id": training_run_id},
        )
        await session.commit()

    # Materialise bronze -> silver -> gold -> walk_forward_fold_results via Dagster.
    _run_dagster_demo_job(training_run_id=training_run_id)

    async with session_scope() as session:
        folds = (
            await session.execute(
                text(
                    """SELECT fold_index, out_of_sample_ic, out_of_sample_sharpe
                       FROM walk_forward_folds
                       WHERE training_run_id = :tr
                       ORDER BY fold_index"""
                ),
                {"tr": training_run_id},
            )
        ).all()

    fold_count = len(folds)
    fold_oos_returns = np.array([f.out_of_sample_sharpe for f in folds])
    pbo_score = pbo(
        np.array([[f.out_of_sample_ic] for f in folds]).repeat(2, axis=1),
        n_partitions=4,
        sharpe_periods_per_year=4,
    )
    dsr_score = deflated_sharpe(fold_oos_returns, num_trials=1)

    version = "demo-v1"
    model_version_id = f"demo-mv-{uuid.uuid4().hex[:8]}"

    async with session_scope() as session:
        await session.execute(
            text(
                """UPDATE training_runs SET status = 'completed', completed_at = now()
                   WHERE id = :id"""
            ),
            {"id": training_run_id},
        )
        # model_versions: id (text PK), mlflow_model_version (not mlflow_run_id)
        await session.execute(
            text(
                """INSERT INTO model_versions
                       (id, model_id, version, stage, training_run_id,
                        mlflow_model_version, pbo, dsr_probability,
                        walk_forward_fold_count)
                   VALUES (:id, 'qlib-lgbm', :v, 'draft', :tr,
                           'mlf-demo-1', :pbo, :dsr, :folds)"""
            ),
            {
                "id": model_version_id,
                "v": version,
                "tr": training_run_id,
                "pbo": float(pbo_score.pbo),
                "dsr": float(dsr_score.probability),
                "folds": fold_count,
            },
        )
        await session.execute(
            text(
                """UPDATE model_versions SET stage = 'production'
                    WHERE model_id = 'qlib-lgbm' AND version = :v"""
            ),
            {"v": version},
        )
        await append_audit_event(
            session,
            actor="demo@example.com",
            event_type="ModelPromoted",
            aggregate_type="ModelVersion",
            aggregate_id=f"qlib-lgbm/{version}",
            payload={"model_id": "qlib-lgbm", "version": version, "reason": "demo seed"},
        )
        # inference_log: actual columns are instrument, as_of_date, feature_hash, prediction
        # (NOT request_payload / response_payload — adapted from plan)
        await session.execute(
            text(
                """INSERT INTO inference_log
                       (id, model_id, model_version, instrument, as_of_date,
                        feature_hash, prediction, latency_ms, requested_by)
                   VALUES (gen_random_uuid(), 'qlib-lgbm', :v,
                           'DEMO_SYN_1', '2024-12-31',
                           'demo-feature-hash-000', 0.0042, 12, 'demo@example.com')"""
            ),
            {"v": version},
        )
        await session.commit()

    return {
        "strategy_id": strategy_id,
        "training_run_id": training_run_id,
        "model_version": version,
        "model_version_id": model_version_id,
        "fold_count": fold_count,
        "pbo": float(pbo_score.pbo),
        "dsr": float(dsr_score.probability),
    }


if __name__ == "__main__":
    result = asyncio.run(run_demo_seed())
    print("Demo seeded successfully:")
    for k, v in result.items():
        print(f"  {k}: {v}")
