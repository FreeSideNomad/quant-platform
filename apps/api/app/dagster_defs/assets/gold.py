"""Gold layer: Alpha158 features."""

from __future__ import annotations

import asyncio
import concurrent.futures
from datetime import date
from typing import Any, Coroutine, TypeVar

from dagster import (
    AssetCheckResult,
    AssetCheckSeverity,
    MaterializeResult,
    asset,
    asset_check,
)
from sqlalchemy import text

from app.dagster_defs.assets.silver import silver_pit_prices
from app.infra.db import session_scope
from app.quant.pipeline import build_gold_features

T = TypeVar("T")


def _run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine safely regardless of whether there is already a running event loop.

    Spawns a fresh OS thread so asyncio.run() always gets a clean event loop.
    Resets the SQLAlchemy engine module-level cache inside the thread so the engine
    is not bound to any other loop's connections.
    """
    import app.infra.db as _db

    def _in_thread() -> T:
        _db._engine = None
        _db._session_factory = None
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_in_thread)
        return future.result()


@asset(deps=[silver_pit_prices], group_name="data", compute_kind="python")
def gold_alpha_features() -> MaterializeResult:
    """Materialise Alpha158 features from silver into features_gold."""

    async def _run() -> int:
        async with session_scope() as session:
            await build_gold_features(session, as_of=date.today())
            count = (
                await session.execute(text("SELECT count(*) FROM features_gold"))
            ).scalar_one()
            await session.commit()
        return int(count)

    rows = _run_async(_run())
    return MaterializeResult(metadata={"row_count": rows})


@asset_check(asset=gold_alpha_features, name="gold_row_count")
def gold_row_count_check() -> AssetCheckResult:
    """Fail if features_gold is empty."""

    async def _count() -> int:
        async with session_scope() as session:
            return int(
                (await session.execute(text("SELECT count(*) FROM features_gold"))).scalar_one()
            )

    n = _run_async(_count())
    return AssetCheckResult(
        passed=n > 0,
        severity=AssetCheckSeverity.ERROR,
        metadata={"row_count": n},
    )
