"""Guards on the bundled apps/api/data/ dataset artefacts.

Three files ship as a coherent unit:
  - aapl_daily.parquet           — the data
  - aapl_daily.meta.json         — content_hash + schema (read by the v1 migration)
  - PROVENANCE.md                — human-readable source / license / fetch info

The migration container has only stdlib + alembic, so it reads
content_hash + schema from the sidecar JSON rather than recomputing
from the parquet bytes. These tests verify the sidecar truthfully
describes the parquet — drift between them means someone edited one
file without re-running scripts/refresh_aapl_data.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import xxhash

API_DIR = Path(__file__).parent.parent
PARQUET = API_DIR / "data" / "aapl_daily.parquet"
META = API_DIR / "data" / "aapl_daily.meta.json"

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


def test_bundled_meta_sidecar_matches_parquet() -> None:
    """Sidecar JSON's content_hash and schema must equal what we'd compute from the parquet."""
    assert META.is_file(), (
        f"missing sidecar metadata at {META}. The v1 migration reads from "
        f"this file — refresh via `uv run python scripts/refresh_aapl_data.py`."
    )
    meta = json.loads(META.read_text())

    expected_hash = xxhash.xxh64(PARQUET.read_bytes()).hexdigest()
    assert meta["content_hash_hex"] == expected_hash, (
        f"sidecar content_hash_hex={meta['content_hash_hex']!r} but "
        f"parquet's actual xxh64={expected_hash!r}. Re-run "
        f"scripts/refresh_aapl_data.py to regenerate both atomically."
    )

    expected_schema = {col: str(dtype) for col, dtype in pl.read_parquet(PARQUET).schema.items()}
    assert meta["schema"] == expected_schema, (
        f"sidecar schema={meta['schema']!r} but "
        f"parquet's actual schema={expected_schema!r}. Re-run "
        f"scripts/refresh_aapl_data.py to regenerate both atomically."
    )
