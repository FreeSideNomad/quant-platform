"""Materialising the walk-forward asset writes the same per-fold rows
as a direct call to train_lgbm_walk_forward."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from datetime import date

import pytest
from sqlalchemy import text

from app.infra.db import session_scope
from app.quant.pipeline import build_gold_features, load_bronze_to_silver
from app.quant.synthetic import DEFAULT_UNIVERSE, SyntheticConfig, generate
from app.quant.training import train_lgbm_walk_forward
from app.quant.walk_forward import WalkForwardConfig


@pytest.fixture(autouse=True)
async def _truncate():
    async with session_scope() as session:
        await session.execute(
            text(
                """TRUNCATE TABLE walk_forward_folds, features_gold,
                                  daily_prices_silver RESTART IDENTITY CASCADE"""
            )
        )
        await session.commit()
    yield


async def _seed_features():
    bars = generate(
        SyntheticConfig(
            instruments=DEFAULT_UNIVERSE,
            start=date(2018, 1, 1),
            end=date(2024, 12, 31),
            seed=42,
        )
    )
    async with session_scope() as session:
        await load_bronze_to_silver(session, bars, backdate_knowable_at=True)
        await build_gold_features(session, as_of=date(2024, 12, 31))
        await session.commit()


@pytest.mark.integration
async def test_dagster_walk_forward_asset_writes_same_folds_as_direct_call():
    await _seed_features()

    cfg = WalkForwardConfig(step="quarter", train_window="3y", test_window="1q", min_folds=4)
    direct = await train_lgbm_walk_forward(
        training_run_id="trun-direct",
        wf_config=cfg,
        as_of=date(2024, 12, 31),
    )

    async with session_scope() as session:
        await session.execute(text("TRUNCATE TABLE walk_forward_folds RESTART IDENTITY"))
        await session.commit()

    dagster_home = tempfile.mkdtemp(prefix="dagster_home_")
    env = {
        **os.environ,
        "DATABASE_URL": os.environ.get(
            "DATABASE_URL", "postgresql+asyncpg://quant:quant@localhost:5433/quant"
        ),
        "DAGSTER_HOME": dagster_home,
    }

    run_config = json.dumps(
        {
            "ops": {
                "walk_forward_fold_results": {
                    "config": {
                        "training_run_id": "trun-dagster",
                        "step": "quarter",
                        "train_window": "3y",
                        "test_window": "1q",
                        "min_folds": 4,
                        "as_of": "2024-12-31",
                    }
                }
            },
            "execution": {"config": {"in_process": {}}},
        }
    )

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
            "walk_forward_fold_results",
            "--config-json",
            run_config,
        ],
        capture_output=True,
        text=True,
        timeout=600,
        cwd="/Users/igormusic/code/deployment/quant-platform/apps/api",
        env=env,
    )
    assert result.returncode == 0, (
        f"dagster materialize failed:\n{result.stderr}\n{result.stdout}"
    )

    async with session_scope() as session:
        rows = (
            await session.execute(
                text(
                    """SELECT fold_index, out_of_sample_ic
                       FROM walk_forward_folds
                       WHERE training_run_id = 'trun-dagster'
                       ORDER BY fold_index"""
                )
            )
        ).all()

    assert len(rows) == direct.fold_count, (
        f"Fold count mismatch: direct={direct.fold_count}, dagster={len(rows)}"
    )
    direct_ics = sorted(f.out_of_sample_ic for f in direct.folds)
    dagster_ics = sorted(r.out_of_sample_ic for r in rows)
    for d, x in zip(direct_ics, dagster_ics, strict=True):
        assert abs(d - x) < 1e-6, f"IC mismatch: direct={d}, dagster={x}"
