"""Integration test for train_lgbm_walk_forward().

Exercises the full pipeline:
  1. Seed synthetic data -> silver -> gold
  2. Run walk-forward training (4+ folds)
  3. Assert per-fold IC metrics exist
  4. Assert rows were persisted to walk_forward_folds
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from app.infra.db import session_scope
from app.quant.pipeline import build_gold_features, load_bronze_to_silver
from app.quant.synthetic import DEFAULT_UNIVERSE, SyntheticConfig, generate
from app.quant.training import train_lgbm_walk_forward
from app.quant.walk_forward import WalkForwardConfig


@pytest.fixture(autouse=True)
async def _truncate_walk_forward_tables():
    """Truncate feature + walk-forward tables before each test for a clean slate."""
    async with session_scope() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE walk_forward_folds, features_gold, daily_prices_silver"
                " RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()
    yield


@pytest.mark.integration
async def test_walk_forward_training_produces_per_fold_metrics():
    # Seed 7 years of synthetic data so 4+ quarterly folds fit.
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

    cfg = WalkForwardConfig(
        step="quarter",
        train_window="3y",
        test_window="1q",
        min_folds=4,
    )
    artefact = await train_lgbm_walk_forward(
        training_run_id="trun-test-1",
        wf_config=cfg,
        as_of=date(2024, 12, 31),
    )

    assert artefact.fold_count >= 4, f"Expected >= 4 folds, got {artefact.fold_count}"
    assert all(
        f.out_of_sample_ic is not None for f in artefact.folds
    ), "All folds must have OOS IC"
    assert artefact.aggregate_oos_ic is not None, "Aggregate OOS IC must be set"
    assert artefact.aggregate_oos_sharpe is not None, "Aggregate OOS Sharpe must be set"

    # Verify the rows were persisted to the database.
    async with session_scope() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT fold_index, out_of_sample_ic
                    FROM walk_forward_folds
                    WHERE training_run_id = 'trun-test-1'
                    ORDER BY fold_index
                    """
                )
            )
        ).all()

    assert len(rows) == artefact.fold_count, (
        f"DB row count {len(rows)} != fold_count {artefact.fold_count}"
    )
    for row, fold in zip(rows, artefact.folds, strict=True):
        assert row.fold_index == fold.index, (
            f"fold_index mismatch: DB={row.fold_index}, artefact={fold.index}"
        )
        assert abs(row.out_of_sample_ic - fold.out_of_sample_ic) < 1e-9, (
            f"OOS IC mismatch at fold {fold.index}: "
            f"DB={row.out_of_sample_ic}, artefact={fold.out_of_sample_ic}"
        )
