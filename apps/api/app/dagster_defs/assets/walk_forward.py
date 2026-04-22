"""Walk-forward training as a Dagster software-defined asset.

walk_forward_fold_results materialises per-fold metrics into walk_forward_folds
via train_lgbm_walk_forward and surfaces the aggregate IC/Sharpe + fold count
as Dagster asset metadata.

The per-fold DynamicOut op (walk_forward_fold_dates_op) is reserved for the
Phase 7 demo_full_lineage job; the asset is the user-facing materialisation
surface.
"""

# NOTE: do NOT add `from __future__ import annotations` here.
# Dagster inspects Config subclass annotations at import time using
# typing.get_type_hints(); the PEP 563 postponed-evaluation behaviour
# introduced by that future import breaks the introspection, causing
# Dagster to reject WalkForwardAssetConfig at startup.

import asyncio
import concurrent.futures
from datetime import date
from typing import Any, Coroutine, TypeVar

from dagster import (
    Config,
    DynamicOut,
    DynamicOutput,
    MaterializeResult,
    asset,
    op,
)

from app.dagster_defs.assets.gold import gold_alpha_features
from app.quant.training import train_lgbm_walk_forward
from app.quant.walk_forward import WalkForwardConfig

T = TypeVar("T")


def _run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine safely regardless of whether there is already a running event loop.

    Spawns a fresh OS thread so asyncio.run() always gets a clean event loop.
    Resets the SQLAlchemy engine module-level cache inside the thread so the
    engine is not bound to any other loop's connections (avoids asyncpg
    "Future attached to a different loop" errors in test).
    """
    import app.infra.db as _db

    def _in_thread() -> T:
        _db._engine = None
        _db._session_factory = None
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_in_thread)
        return future.result()


class WalkForwardAssetConfig(Config):
    training_run_id: str
    step: str = "quarter"
    train_window: str = "3y"
    test_window: str = "1q"
    min_folds: int = 4
    as_of: str  # YYYY-MM-DD


@asset(
    deps=[gold_alpha_features],
    group_name="training",
    compute_kind="lightgbm",
)
def walk_forward_fold_results(config: WalkForwardAssetConfig) -> MaterializeResult:
    """Materialises per-fold metrics into walk_forward_folds.

    Implementation reuses train_lgbm_walk_forward (Task 3.3) which
    already loops folds, trains, and persists. The asset wrapper
    surfaces the aggregate IC/Sharpe + fold count as Dagster metadata
    so they appear in the lineage UI; per-fold rows remain in Postgres.
    """
    cfg = WalkForwardConfig(
        step=config.step,
        train_window=config.train_window,
        test_window=config.test_window,
        min_folds=config.min_folds,
    )

    artefact = _run_async(
        train_lgbm_walk_forward(
            training_run_id=config.training_run_id,
            wf_config=cfg,
            as_of=date.fromisoformat(config.as_of),
        )
    )

    return MaterializeResult(
        metadata={
            "training_run_id": artefact.training_run_id,
            "fold_count": artefact.fold_count,
            "aggregate_oos_ic": artefact.aggregate_oos_ic,
            "aggregate_oos_sharpe": artefact.aggregate_oos_sharpe,
            "first_fold_test_start": artefact.folds[0].test_start.isoformat(),
            "last_fold_test_end": artefact.folds[-1].test_end.isoformat(),
        },
    )


# --- Per-fold dynamic graph (used by demo_full_lineage in Phase 7) ---


@op(out=DynamicOut())
def walk_forward_fold_dates_op(config: WalkForwardAssetConfig):
    """Yield one DynamicOutput per fold so subsequent ops fan out."""
    from sqlalchemy import text as _text

    from app.infra.db import session_scope as _session_scope
    from app.quant.walk_forward import fold_dates

    cfg = WalkForwardConfig(
        step=config.step,
        train_window=config.train_window,
        test_window=config.test_window,
        min_folds=config.min_folds,
    )

    async def _bounds() -> tuple[date, date]:
        async with _session_scope() as session:
            row = (
                await session.execute(
                    _text("SELECT min(trade_date), max(trade_date) FROM features_gold")
                )
            ).one()
        return row[0], min(row[1], date.fromisoformat(config.as_of))

    data_start, data_end = _run_async(_bounds())
    for fold in fold_dates(cfg, data_start=data_start, data_end=data_end):
        yield DynamicOutput(
            value={
                "training_run_id": config.training_run_id,
                "index": fold.index,
                "train_start": fold.train_start.isoformat(),
                "train_end": fold.train_end.isoformat(),
                "test_start": fold.test_start.isoformat(),
                "test_end": fold.test_end.isoformat(),
            },
            mapping_key=f"fold_{fold.index}",
        )


__all__ = [
    "WalkForwardAssetConfig",
    "walk_forward_fold_dates_op",
    "walk_forward_fold_results",
]
