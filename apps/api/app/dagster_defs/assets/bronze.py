"""Bronze layer: raw synthetic OHLCV bars."""

import asyncio
import concurrent.futures
import uuid
from datetime import date
from typing import Any, Coroutine, TypeVar

from dagster import Config, MaterializeResult, asset

from app.quant.synthetic import DEFAULT_UNIVERSE, SyntheticConfig, generate

T = TypeVar("T")


def _run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine safely regardless of whether there is already a running event loop.

    Spawns a fresh OS thread so asyncio.run() always gets a clean event loop.
    """

    def _in_thread() -> T:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_in_thread)
        return future.result()


class BronzeConfig(Config):
    start: str = "2018-01-01"
    end: str = "2024-12-31"
    seed: int = 42


@asset(group_name="data", compute_kind="python")
def bronze_synthetic_universe(config: BronzeConfig) -> MaterializeResult:
    """Generate the synthetic universe and stash it in a deterministic cache.

    The cache is read by silver_pit_prices on the next compute. We
    cache rather than passing through Dagster IO managers so the
    direct-Python and Dagster-orchestrated paths share state.
    """
    bars = generate(
        SyntheticConfig(
            instruments=DEFAULT_UNIVERSE,
            start=date.fromisoformat(config.start),
            end=date.fromisoformat(config.end),
            seed=config.seed,
        )
    )
    from app.quant.pipeline import write_bronze_cache

    cache_key = uuid.uuid4().hex
    _run_async(write_bronze_cache(bars, key=cache_key))

    return MaterializeResult(
        metadata={
            "row_count": len(bars),
            "start": config.start,
            "end": config.end,
            "seed": config.seed,
            "cache_key": cache_key,
        }
    )
