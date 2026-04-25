"""Sanity check on the bundled apps/api/data/aapl_daily.parquet.

This test used to assert the migration's hard-coded `content_hash` and
`schema_json` literals matched the parquet's actual bytes/schema. The
v1 migration now derives both at upgrade time directly from the parquet,
so drift between registered metadata and actual data is structurally
impossible — the migration IS the guard.

What's left to check is the existence and basic shape of the bundled
file itself (file present, readable as parquet, has the columns the
SDK expects). Refresh via `uv run python scripts/refresh_aapl_data.py`.
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

API_DIR = Path(__file__).parent.parent
PARQUET = API_DIR / "data" / "aapl_daily.parquet"

# Columns the SDK expects (data.ohlcv() returns these). Keeping this list
# here as the explicit contract: if a future refresh script changes the
# schema, this assertion catches it before the migration runs.
EXPECTED_COLUMNS = {"date", "open", "high", "low", "close", "adj_close", "volume"}


def test_bundled_parquet_exists_and_has_expected_columns() -> None:
    assert PARQUET.is_file(), (
        f"missing bundled parquet at {PARQUET}. "
        f"Refresh via `uv run python scripts/refresh_aapl_data.py` "
        f"(maintainer; needs Kaggle API token in KAGGLE_API_TOKEN)."
    )
    df = pl.read_parquet(PARQUET)
    actual_columns = set(df.columns)
    missing = EXPECTED_COLUMNS - actual_columns
    extra = actual_columns - EXPECTED_COLUMNS
    assert not missing, f"bundled parquet missing expected columns: {missing}"
    assert not extra, (
        f"bundled parquet has unexpected columns {extra} — "
        f"the SDK contract is exactly {EXPECTED_COLUMNS}; widen this test "
        f"deliberately if the SDK is being extended."
    )
    assert df.height > 0, "bundled parquet has zero rows"
