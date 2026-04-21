"""Deterministic synthetic OHLCV generator.

Generates a geometric-Brownian-motion-ish daily series for a small universe.
Reproducible by `seed`, stable across runs — so training runs can be compared
like-for-like without a real data feed. Swap for a real bronze loader (Qlib
data dump, Bloomberg BPIPE, vendor SFTP, etc.) without changing the silver
transformation or downstream pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import polars as pl


@dataclass(frozen=True)
class SyntheticConfig:
    instruments: tuple[str, ...]
    start: date
    end: date
    seed: int = 42
    start_price: float = 100.0
    mu_annual: float = 0.08
    sigma_annual: float = 0.20


def _trading_days(start: date, end: date) -> list[date]:
    out: list[date] = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def generate(config: SyntheticConfig) -> pl.DataFrame:
    rng = np.random.default_rng(config.seed)
    days = _trading_days(config.start, config.end)
    n_days = len(days)
    trading_days_per_year = 252
    mu_daily = config.mu_annual / trading_days_per_year
    sigma_daily = config.sigma_annual / np.sqrt(trading_days_per_year)

    rows: list[dict[str, object]] = []
    for i, instrument in enumerate(config.instruments):
        instrument_rng = np.random.default_rng(config.seed + i)
        # Small drift variation per instrument so Alphas differ.
        mu_i = mu_daily * (1.0 + 0.1 * i / max(len(config.instruments) - 1, 1))
        sigma_i = sigma_daily * (1.0 + 0.05 * i / max(len(config.instruments) - 1, 1))

        returns = instrument_rng.normal(mu_i, sigma_i, n_days)
        close = config.start_price * np.exp(np.cumsum(returns))
        prev_close = np.concatenate(([config.start_price], close[:-1]))

        intraday_vol = np.abs(instrument_rng.normal(0, sigma_i * 0.6, n_days))
        open_ = prev_close * np.exp(instrument_rng.normal(0, sigma_i * 0.3, n_days))
        high = np.maximum(open_, close) * (1 + intraday_vol)
        low = np.minimum(open_, close) * (1 - intraday_vol)
        volume = instrument_rng.lognormal(mean=13, sigma=0.6, size=n_days)

        for j, d in enumerate(days):
            rows.append(
                {
                    "instrument": instrument,
                    "trade_date": d,
                    "open": float(open_[j]),
                    "high": float(high[j]),
                    "low": float(low[j]),
                    "close": float(close[j]),
                    "volume": float(volume[j]),
                    "adj_close": float(close[j]),
                }
            )

    return pl.DataFrame(rows)


DEFAULT_UNIVERSE: tuple[str, ...] = ("QPX.A", "QPX.B", "QPX.C", "QPX.D", "QPX.E")
