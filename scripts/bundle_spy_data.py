"""Generate a synthetic ~10y daily OHLCV parquet labelled spy_daily for the MVP demo.

Deterministic (numpy seed=20260424). NOT real SPY data — see dataset
description in migration 0002. Regenerate anytime by rerunning:
  uv run python scripts/bundle_spy_data.py
"""
from __future__ import annotations
from datetime import date, timedelta
from pathlib import Path
import numpy as np
import polars as pl


def generate_synthetic_ohlcv(
    *,
    start_date: date = date(2014, 12, 1),
    n_days: int = 2518,   # ~10 years of trading days
    seed: int = 20260424,
    initial_price: float = 200.0,
    annual_drift: float = 0.08,
    base_annual_vol: float = 0.18,
) -> pl.DataFrame:
    rng = np.random.default_rng(seed)

    # GARCH-like vol clustering: AR(1) on log-vol
    log_vol = np.zeros(n_days)
    log_vol[0] = np.log(base_annual_vol / np.sqrt(252))
    phi = 0.95
    sigma_vol = 0.08
    for t in range(1, n_days):
        log_vol[t] = phi * log_vol[t - 1] + (1 - phi) * np.log(base_annual_vol / np.sqrt(252)) + sigma_vol * rng.standard_normal()
    daily_vol = np.exp(log_vol)

    # Log returns with clustering vol
    mu_daily = annual_drift / 252
    log_returns = mu_daily + daily_vol * rng.standard_normal(n_days)
    close = initial_price * np.exp(np.cumsum(log_returns))

    # Open ~= previous close + small gap
    gap = rng.normal(0, 0.001, n_days) * close
    open_ = np.concatenate([[initial_price], close[:-1]]) + gap

    # High/low around max/min of open/close plus intrabar range
    intrabar_range = np.abs(rng.normal(0, 1, n_days)) * daily_vol * close
    high = np.maximum(open_, close) + intrabar_range * 0.6
    low = np.minimum(open_, close) - intrabar_range * 0.4
    low = np.maximum(low, 0.01)  # no negative prices

    # adj_close == close (no splits/dividends in synthetic data)
    adj_close = close

    # Volume: log-normal around 80M shares, anti-correlated with returns
    volume = rng.lognormal(mean=np.log(80e6), sigma=0.35, size=n_days)
    volume = volume * (1 + 0.5 * np.abs(log_returns / log_returns.std()))
    volume = volume.astype(np.int64)

    # Dates: business days only (approx — skip Sat/Sun)
    dates = []
    d = start_date
    while len(dates) < n_days:
        if d.weekday() < 5:
            dates.append(d)
        d += timedelta(days=1)

    return pl.DataFrame({
        "date": dates,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "adj_close": adj_close,
        "volume": volume,
    })


def main() -> None:
    out = Path("apps/api/data/spy_daily.parquet")
    out.parent.mkdir(parents=True, exist_ok=True)
    df = generate_synthetic_ohlcv()
    df.write_parquet(out, compression="snappy")
    size_kb = out.stat().st_size / 1024
    print(f"Wrote {out} ({df.height:,} rows, {size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
