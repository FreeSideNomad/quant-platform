"""Guards on the bundled apps/api/data/spy_daily.parquet seed row in
migration 0002:

  1. The hex content_hash in the migration must equal the xxh64 of the
     parquet bytes. If scripts/bundle_spy_data.py is rerun and the
     parquet changes, the printed xxh64 hash must be pasted into the
     migration literal — this test fails until it is.

  2. The schema_json in the migration must equal the actual polars
     schema of the parquet. Drift here means the registered dataset
     contract no longer describes the data on disk; SDK code reads
     from the registered schema, so silent drift would propagate to
     model signatures.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import polars as pl
import xxhash

API_DIR = Path(__file__).parent.parent
PARQUET = API_DIR / "data" / "spy_daily.parquet"
MIGRATION = API_DIR / "migrations" / "versions" / "0002_m3_schema.py"


def test_migration_content_hash_matches_bundled_parquet() -> None:
    assert PARQUET.is_file(), f"missing bundled parquet at {PARQUET}"
    expected = xxhash.xxh64(PARQUET.read_bytes()).hexdigest()

    src = MIGRATION.read_text()
    # Find `\xNNNNNNNNNNNNNNNN'::bytea` next to the SPY seed INSERT
    matches = re.findall(r"'\\x([0-9a-fA-F]{16})'::bytea", src)
    assert matches, "no BYTEA hex literal found in migration 0002 — did the seed INSERT change shape?"
    # The dataset_versions seed is the only BYTEA literal we hard-code in this migration
    assert expected in [m.lower() for m in matches], (
        f"migration 0002 hard-codes content_hash(es) {matches} "
        f"but the bundled parquet's xxh64 is {expected}. "
        f"Either the parquet was regenerated (update the migration literal) "
        f"or the migration drifted (regenerate via scripts/bundle_spy_data.py)."
    )


def test_migration_schema_json_matches_bundled_parquet() -> None:
    """schema_json literals in migration 0002 must equal the parquet's actual schema."""
    assert PARQUET.is_file(), f"missing bundled parquet at {PARQUET}"
    actual_schema = {col: str(dtype) for col, dtype in pl.read_parquet(PARQUET).schema.items()}

    src = MIGRATION.read_text()
    # Both `datasets.schema_json` and `dataset_versions.schema_json` should
    # carry the column→dtype map. Pull every JSONB literal from the file
    # and require at least one to match the parquet's schema verbatim.
    jsonb_literals = re.findall(r"'(\{[^']*\})'::jsonb", src)
    parsed = []
    for lit in jsonb_literals:
        try:
            parsed.append(json.loads(lit))
        except json.JSONDecodeError:
            continue

    assert actual_schema in parsed, (
        f"migration 0002 schema_json literals {parsed} do not include the "
        f"bundled parquet's actual schema {actual_schema}. The seed INSERT "
        f"for the SPY dataset must carry the real column→dtype map; SDK "
        f"code reads from this row to build MLflow signatures, so drift "
        f"here will silently produce wrong signatures."
    )
