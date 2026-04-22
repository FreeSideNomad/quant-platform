"""Silver layer: PIT-corrected prices with knowable_at."""

import asyncio
import concurrent.futures
from typing import Any, Coroutine, TypeVar

from dagster import (
    AssetCheckResult,
    AssetCheckSeverity,
    AssetExecutionContext,
    AssetKey,
    MaterializeResult,
    asset,
    asset_check,
)
from sqlalchemy import text

from app.dagster_defs.assets.bronze import bronze_synthetic_universe
from app.infra.db import session_scope
from app.quant.pipeline import load_bronze_to_silver, read_bronze_cache

T = TypeVar("T")


def _run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine safely regardless of whether there is already a running event loop.

    Spawns a fresh OS thread so asyncio.run() always gets a clean event loop.
    Resets the SQLAlchemy engine module-level cache inside the thread so the engine
    is not bound to any other loop's connections.
    """
    import app.infra.db as _db

    def _in_thread() -> T:
        # Reset the global engine so it is re-created in this thread's event loop.
        # This avoids "Future attached to a different loop" errors from asyncpg.
        _db._engine = None
        _db._session_factory = None
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_in_thread)
        return future.result()


@asset(deps=[bronze_synthetic_universe], group_name="data", compute_kind="sql")
def silver_pit_prices(context: AssetExecutionContext) -> MaterializeResult:
    """Load the bronze cache into daily_prices_silver with backdate_knowable_at=True."""
    # Retrieve the cache_key written by the upstream bronze materialization.
    upstream_event = context.instance.get_latest_materialization_event(
        AssetKey("bronze_synthetic_universe")
    )
    if upstream_event is None or upstream_event.asset_materialization is None:
        raise RuntimeError("No bronze materialization event found; run bronze first.")
    cache_key = upstream_event.asset_materialization.metadata["cache_key"].value

    async def _run() -> int:
        bars = await read_bronze_cache(cache_key)
        async with session_scope() as session:
            await load_bronze_to_silver(session, bars, backdate_knowable_at=True)
            count = (
                await session.execute(text("SELECT count(*) FROM daily_prices_silver"))
            ).scalar_one()
            await session.commit()
        return int(count)

    rows = _run_async(_run())
    return MaterializeResult(metadata={"row_count": rows})


@asset_check(asset=silver_pit_prices, name="pit_integrity")
def pit_integrity_check() -> AssetCheckResult:
    """Fail if any silver row's knowable_at is in the future relative to its trade_date."""

    async def _run() -> tuple[bool, int]:
        async with session_scope() as session:
            bad = (
                await session.execute(
                    text(
                        "SELECT count(*) FROM daily_prices_silver "
                        "WHERE knowable_at::date > trade_date"
                    )
                )
            ).scalar_one()
        return bad == 0, int(bad)

    passed, bad_rows = _run_async(_run())
    return AssetCheckResult(
        passed=passed,
        severity=AssetCheckSeverity.ERROR,
        metadata={"future_knowable_rows": bad_rows},
    )
