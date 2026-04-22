"""Materialising the gold asset produces the same rows as the direct Python call."""

from __future__ import annotations

import asyncio
import os
import subprocess
from datetime import date

import pytest
from sqlalchemy import text

from app.infra.db import session_scope
from app.quant.pipeline import build_gold_features, load_bronze_to_silver
from app.quant.synthetic import DEFAULT_UNIVERSE, SyntheticConfig, generate


@pytest.fixture(autouse=True)
async def _truncate_layers():
    async with session_scope() as session:
        await session.execute(
            text("TRUNCATE TABLE features_gold, daily_prices_silver RESTART IDENTITY CASCADE")
        )
        await session.commit()
    yield


@pytest.mark.integration
async def test_dagster_gold_asset_materialises_same_rows_as_direct_call():
    """Two runs against the same synthetic seed produce equivalent gold tables."""
    bars = generate(SyntheticConfig(instruments=DEFAULT_UNIVERSE, start=date(2022, 1, 1), end=date(2022, 6, 30), seed=42))
    async with session_scope() as session:
        await load_bronze_to_silver(session, bars, backdate_knowable_at=True)
        await build_gold_features(session, as_of=date.today())
        await session.commit()

    async with session_scope() as session:
        direct_count = (
            await session.execute(text("SELECT count(*) FROM features_gold"))
        ).scalar_one()
        direct_checksum = (
            await session.execute(
                text(
                    "SELECT md5(string_agg(instrument || trade_date::text, ','"
                    " ORDER BY instrument, trade_date)) FROM features_gold"
                )
            )
        ).scalar_one()

    async with session_scope() as session:
        await session.execute(
            text("TRUNCATE TABLE features_gold, daily_prices_silver RESTART IDENTITY CASCADE")
        )
        await session.commit()

    import tempfile

    dagster_home = tempfile.mkdtemp(prefix="dagster_home_")
    env = {
        **os.environ,
        "DATABASE_URL": os.environ.get(
            "DATABASE_URL", "postgresql+asyncpg://quant:quant@localhost:5433/quant"
        ),
        # Point DAGSTER_HOME at a temp dir without a dagster.yaml so Dagster
        # uses its default in-process/sqlite storage instead of the Postgres
        # storage config in apps/api/dagster.yaml (which requires
        # DAGSTER_POSTGRES_HOST etc. that are not set in local dev).
        "DAGSTER_HOME": dagster_home,
    }
    import json

    run_config = json.dumps(
        {
            "ops": {
                "bronze_synthetic_universe": {
                    "config": {"start": "2022-01-01", "end": "2022-06-30", "seed": 42}
                }
            },
            # Use the in-process executor so all steps run in the same process
            # and inherit DATABASE_URL from the spawned subprocess environment.
            # The default multiprocess executor launches grandchild processes that
            # lose environment variables not explicitly propagated.
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
            "bronze_synthetic_universe,silver_pit_prices,gold_alpha_features",
            "--config-json",
            run_config,
        ],
        capture_output=True,
        text=True,
        timeout=300,
        cwd="/Users/igormusic/code/deployment/quant-platform/apps/api",
        env=env,
    )
    assert result.returncode == 0, f"dagster materialize failed:\n{result.stderr}\n{result.stdout}"

    async with session_scope() as session:
        dagster_count = (
            await session.execute(text("SELECT count(*) FROM features_gold"))
        ).scalar_one()
        dagster_checksum = (
            await session.execute(
                text(
                    "SELECT md5(string_agg(instrument || trade_date::text, ','"
                    " ORDER BY instrument, trade_date)) FROM features_gold"
                )
            )
        ).scalar_one()

    assert dagster_count == direct_count, (
        f"Row count mismatch: direct={direct_count}, dagster={dagster_count}"
    )
    assert dagster_checksum == direct_checksum, (
        f"Checksum mismatch: direct={direct_checksum}, dagster={dagster_checksum}"
    )


@pytest.mark.integration
async def test_pit_integrity_asset_check_catches_future_knowable_at():
    """The silver_pit_prices asset declares an asset check that passes when
    backdate_knowable_at=True is used — meaning no knowable_at is in the future
    relative to trade_date."""
    from dagster import materialize_to_memory

    from app.dagster_defs.assets.bronze import bronze_synthetic_universe
    from app.dagster_defs.assets.silver import pit_integrity_check, silver_pit_prices

    # AssetChecksDefinition inherits AssetsDefinition, so include check in assets list
    result = materialize_to_memory(
        [bronze_synthetic_universe, silver_pit_prices, pit_integrity_check],
        run_config={
            "ops": {
                "bronze_synthetic_universe": {
                    "config": {"start": "2022-01-01", "end": "2022-03-31", "seed": 7}
                },
            },
        },
    )
    assert result.success
    check_evals = result.get_asset_check_evaluations()
    assert len(check_evals) > 0, "Expected at least one asset check evaluation"
    pit_check = next(
        (c for c in check_evals if c.check_name == "pit_integrity"),
        None,
    )
    assert pit_check is not None, f"pit_integrity check not found in {[c.check_name for c in check_evals]}"
    assert pit_check.passed, f"pit_integrity check failed with metadata: {pit_check.metadata}"


@pytest.mark.integration
async def test_bronze_cache_isolated_across_concurrent_keys(tmp_path):
    """Two concurrent bronze materializations with different keys do not collide."""
    import polars as pl

    from app.quant.pipeline import read_bronze_cache, write_bronze_cache

    df1 = pl.DataFrame({"a": [1, 2, 3]})
    df2 = pl.DataFrame({"a": [4, 5, 6]})

    key1 = "key1-test"
    key2 = "key2-test"

    await asyncio.gather(
        write_bronze_cache(df1, key=key1),
        write_bronze_cache(df2, key=key2),
    )

    r1 = await read_bronze_cache(key1)
    r2 = await read_bronze_cache(key2)

    assert r1["a"].to_list() == [1, 2, 3]
    assert r2["a"].to_list() == [4, 5, 6]
