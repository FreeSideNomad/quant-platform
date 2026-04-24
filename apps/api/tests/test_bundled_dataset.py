"""Guard: the hex content_hash in migration 0002 must equal the xxh64 of the
bundled apps/api/data/spy_daily.parquet file.

If scripts/bundle_spy_data.py is rerun and the parquet changes, the
printed xxh64 hash must be pasted into the migration literal — this
test fails until it is.
"""
from __future__ import annotations

import re
from pathlib import Path

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
