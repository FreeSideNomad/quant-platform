"""Bronze → silver → gold for the demo workload.

Public entry points:
  - `load_bronze_to_silver()`  — write synthetic OHLCV (or any DataFrame) into
    the silver `daily_prices_silver` table, with bi-temporal `knowable_at`.
  - `build_gold_features(as_of)` — materialise Alpha features and forward
    targets into `features_gold` using data where `knowable_at <= as_of`.
  - `write_bronze_cache(bars, *, key)` — persist the bronze DataFrame to a
    per-key path in /tmp for cross-process handoff between bronze and silver
    Dagster assets.  Returns the Path written.
  - `read_bronze_cache(key)` — read the persisted bronze DataFrame for `key`.

Feature set — a minimal Alpha-shape signal basket inspired by Qlib's Alpha158
family. Small enough to be readable, big enough to actually carry signal:

  mom_5         :  5-day log-return
  mom_20        : 20-day log-return
  vol_20        : 20-day realised volatility of daily log-returns
  return_mean_20: 20-day mean of daily log-returns
  hl_range      : (high-low)/close, intraday volatility proxy
  vol_ratio_20  : volume / 20-day moving average of volume
  target_fwd_1d : next-day log-return (training target; NaN at series tail)
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Final

import numpy as np
import polars as pl
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_BRONZE_CACHE_DIR: Final[Path] = Path("/tmp")


def _bronze_cache_path(key: str) -> Path:
    return _BRONZE_CACHE_DIR / f"bronze_cache_{key}.parquet"


async def write_bronze_cache(bars: pl.DataFrame, *, key: str) -> Path:
    """Persist bronze frame to a per-key location for cross-process handoff."""
    path = _bronze_cache_path(key)
    await asyncio.to_thread(bars.write_parquet, path)
    return path


async def read_bronze_cache(key: str) -> pl.DataFrame:
    """Read the bronze frame for a given key."""
    path = _bronze_cache_path(key)
    return await asyncio.to_thread(pl.read_parquet, path)


async def ensure_instruments(session: AsyncSession, instruments: list[str]) -> None:
    for i, instrument in enumerate(instruments):
        await session.execute(
            text(
                """
                INSERT INTO instruments(instrument, market, listed_at, display_name)
                VALUES (:i, 'SYNTH', '2020-01-01', :n)
                ON CONFLICT (instrument) DO NOTHING
                """
            ),
            {"i": instrument, "n": f"Synthetic {chr(65 + i)}"},
        )


async def load_bronze_to_silver(
    session: AsyncSession,
    df: pl.DataFrame,
    *,
    source_uri: str | None = None,
    backdate_knowable_at: bool = False,
) -> int:
    """Upsert rows into daily_prices_silver. Idempotent on (instrument, trade_date).

    When `backdate_knowable_at=True`, each row's `knowable_at` is set to the end
    of its trade_date (UTC). This is the correct semantics for historical
    backfills — for live streaming loads, leave it False so `knowable_at = now()`.
    """
    rows = df.to_dicts()
    if not rows:
        return 0

    await ensure_instruments(session, sorted({str(r["instrument"]) for r in rows}))

    def _knowable_at(td: date) -> datetime:
        if backdate_knowable_at:
            return datetime.combine(td, time(23, 59, 59, tzinfo=UTC))
        return datetime.now(UTC)

    await session.execute(
        text(
            """
            INSERT INTO daily_prices_silver(
              instrument, trade_date, open, high, low, close, volume, adj_close,
              knowable_at, source_uri
            ) VALUES (
              :instrument, :trade_date, :open, :high, :low, :close, :volume, :adj_close,
              :knowable_at, :src
            )
            ON CONFLICT (instrument, trade_date) DO UPDATE SET
              open = excluded.open,
              high = excluded.high,
              low = excluded.low,
              close = excluded.close,
              volume = excluded.volume,
              adj_close = excluded.adj_close,
              knowable_at = excluded.knowable_at,
              source_uri = excluded.source_uri
            """
        ),
        [
            {
                "instrument": r["instrument"],
                "trade_date": r["trade_date"],
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["volume"]),
                "adj_close": float(r["adj_close"]),
                "knowable_at": _knowable_at(r["trade_date"]),
                "src": source_uri,
            }
            for r in rows
        ],
    )
    return len(rows)


def _alpha_features(prices: pl.DataFrame) -> pl.DataFrame:
    """Compute features and forward target from a price panel."""
    required = {"instrument", "trade_date", "close", "high", "low", "volume"}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"missing columns: {missing}")

    # Per-instrument rolling features
    prices = prices.sort(["instrument", "trade_date"])
    log_close = prices.with_columns(pl.col("close").log().alias("log_close"))
    log_returns = log_close.with_columns(
        pl.col("log_close").diff().over("instrument").alias("log_return")
    )

    out = log_returns.with_columns(
        (pl.col("log_close") - pl.col("log_close").shift(5).over("instrument")).alias("mom_5"),
        (pl.col("log_close") - pl.col("log_close").shift(20).over("instrument")).alias("mom_20"),
        pl.col("log_return").rolling_std(window_size=20).over("instrument").alias("vol_20"),
        pl.col("log_return")
        .rolling_mean(window_size=20)
        .over("instrument")
        .alias("return_mean_20"),
        ((pl.col("high") - pl.col("low")) / pl.col("close")).alias("hl_range"),
        (pl.col("volume") / pl.col("volume").rolling_mean(window_size=20).over("instrument")).alias(
            "vol_ratio_20"
        ),
        # Next-day log return as the training target
        pl.col("log_return").shift(-1).over("instrument").alias("target_fwd_1d"),
    )

    return out.select(
        "instrument",
        "trade_date",
        "mom_5",
        "mom_20",
        "vol_20",
        "return_mean_20",
        "hl_range",
        "vol_ratio_20",
        "target_fwd_1d",
    )


async def build_gold_features(
    session: AsyncSession,
    *,
    as_of: date,
) -> int:
    """Read silver as-of `as_of`, compute features, write to features_gold."""
    rows = await session.execute(
        text(
            """
            SELECT instrument, trade_date, open, high, low, close, volume, adj_close
            FROM daily_prices_silver
            WHERE knowable_at <= CAST(:as_of AS timestamptz) + interval '23:59:59'
            ORDER BY instrument, trade_date
            """
        ),
        {"as_of": as_of},
    )
    data = rows.fetchall()
    if not data:
        return 0

    df = pl.DataFrame(
        {
            "instrument": [r[0] for r in data],
            "trade_date": [r[1] for r in data],
            "open": [r[2] for r in data],
            "high": [r[3] for r in data],
            "low": [r[4] for r in data],
            "close": [r[5] for r in data],
            "volume": [r[6] for r in data],
        }
    )
    features = _alpha_features(df)

    # Drop rows with any NaN in features (the rolling-window warm-up period)
    # but retain rows where only target is NaN (last day of each series) so
    # that inference at the latest known date still has features available.
    feature_cols = ["mom_5", "mom_20", "vol_20", "return_mean_20", "hl_range", "vol_ratio_20"]
    features = features.filter(
        ~pl.any_horizontal([pl.col(c).is_nan() | pl.col(c).is_null() for c in feature_cols])
    )

    records = features.to_dicts()
    if not records:
        return 0

    # The feature row is knowable at the end of its trade_date (the target
    # itself is not revealed until the next day's close; this is captured by
    # the target's own forward shift rather than by a separate knowable_at).
    def _knowable_at(td: date) -> datetime:
        return datetime.combine(td, time(23, 59, 59, tzinfo=UTC))

    await session.execute(
        text(
            """
            INSERT INTO features_gold(
              instrument, trade_date, mom_5, mom_20, vol_20, return_mean_20,
              hl_range, vol_ratio_20, target_fwd_1d, knowable_at
            ) VALUES (:instrument, :trade_date, :mom_5, :mom_20, :vol_20, :return_mean_20,
                      :hl_range, :vol_ratio_20, :target_fwd_1d, :knowable_at)
            ON CONFLICT (instrument, trade_date) DO UPDATE SET
              mom_5 = excluded.mom_5,
              mom_20 = excluded.mom_20,
              vol_20 = excluded.vol_20,
              return_mean_20 = excluded.return_mean_20,
              hl_range = excluded.hl_range,
              vol_ratio_20 = excluded.vol_ratio_20,
              target_fwd_1d = excluded.target_fwd_1d,
              knowable_at = excluded.knowable_at
            """
        ),
        [
            {
                "instrument": r["instrument"],
                "trade_date": r["trade_date"],
                "mom_5": _maybe_float(r.get("mom_5")),
                "mom_20": _maybe_float(r.get("mom_20")),
                "vol_20": _maybe_float(r.get("vol_20")),
                "return_mean_20": _maybe_float(r.get("return_mean_20")),
                "hl_range": _maybe_float(r.get("hl_range")),
                "vol_ratio_20": _maybe_float(r.get("vol_ratio_20")),
                "target_fwd_1d": _maybe_float(r.get("target_fwd_1d")),
                "knowable_at": _knowable_at(r["trade_date"]),
            }
            for r in records
        ],
    )
    return len(records)


def _maybe_float(v: object) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if np.isnan(f):
        return None
    return f


FEATURE_COLUMNS: tuple[str, ...] = (
    "mom_5",
    "mom_20",
    "vol_20",
    "return_mean_20",
    "hl_range",
    "vol_ratio_20",
)
