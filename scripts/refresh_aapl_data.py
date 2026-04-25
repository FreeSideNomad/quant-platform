"""Refresh apps/api/data/aapl_daily.parquet from the Kaggle CC0 dataset.

Source: https://www.kaggle.com/datasets/jacksoncrow/stock-market-dataset
License: CC0 Public Domain (verified 2026-04-25)

The bundled parquet is the ONE-AND-ONLY copy that ships with the platform;
end users never need a Kaggle account. This script exists so a maintainer
can re-fetch when needed (new ticker, license re-verification, etc.).

Prerequisites (one-time):
  1. kaggle.com → Account → "Create New API Token" → downloads kaggle.json
  2. mkdir -p ~/.kaggle && mv ~/Downloads/kaggle.json ~/.kaggle/
  3. chmod 600 ~/.kaggle/kaggle.json

Run:
  uv run python scripts/refresh_aapl_data.py

After it succeeds, you'll see:
  - apps/api/data/aapl_daily.parquet   (bundled with the repo)
  - printed xxh64 content_hash to paste into the v1 migration's seed INSERT
  - printed polars schema to paste into the v1 migration's schema_json literals
The test_bundled_dataset.py guards both.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import polars as pl
import xxhash

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "apps" / "api" / "data"
OUT_PARQUET = DATA_DIR / "aapl_daily.parquet"
META_PATH = DATA_DIR / "aapl_daily.meta.json"
PROVENANCE_PATH = DATA_DIR / "PROVENANCE.md"

KAGGLE_DATASET = "jacksoncrow/stock-market-dataset"
KAGGLE_FILE_PATH = "stocks/AAPL.csv"
TICKER = "AAPL"


def main() -> None:
    # Lazy import: kagglehub isn't a SDK runtime dep, only a maintainer tool
    try:
        import kagglehub
    except ImportError:
        raise SystemExit(
            "kagglehub not installed. Run: uv add --dev kagglehub\n"
            "(or pip install kagglehub in your maintainer venv)"
        )

    # kagglehub accepts auth via either ~/.kaggle/kaggle.json (legacy) or the
    # KAGGLE_API_TOKEN env var (new personal-access-token flow). Don't pre-check;
    # let kagglehub raise its own clearer auth error if neither is configured.

    print(f"Downloading {KAGGLE_DATASET}/{KAGGLE_FILE_PATH} from Kaggle...")
    # kagglehub.dataset_download returns a directory containing the entire dataset.
    # We could use kagglehub.load_dataset for single-file but the API is unstable
    # across kagglehub versions; download then extract is reliable.
    with tempfile.TemporaryDirectory() as td:
        local_dataset_dir = Path(
            kagglehub.dataset_download(KAGGLE_DATASET, path=KAGGLE_FILE_PATH)
        )
        # Some kagglehub versions return the file path directly when `path=` is set.
        if local_dataset_dir.is_file():
            csv_path = local_dataset_dir
        else:
            csv_path = local_dataset_dir / KAGGLE_FILE_PATH
            if not csv_path.is_file():
                raise SystemExit(
                    f"Could not locate {KAGGLE_FILE_PATH} after download. "
                    f"kagglehub returned: {local_dataset_dir} (contents: "
                    f"{list(local_dataset_dir.iterdir())[:10] if local_dataset_dir.is_dir() else 'N/A'})"
                )

        # Stage the CSV in tempdir so we can inspect it without polluting the repo
        staged_csv = Path(td) / f"{TICKER}.csv"
        shutil.copy(csv_path, staged_csv)

        # Read with polars, normalise column names to lowercase + adj_close
        # (matches the prior bundled schema so SDK consumers don't change).
        df = pl.read_csv(staged_csv)
        df = df.rename({c: c.lower().replace(" ", "_") for c in df.columns})
        # Coerce types: Date column → pl.Date; OHLC + Adj Close → Float64; Volume → Int64.
        df = df.with_columns(
            [
                pl.col("date").str.strptime(pl.Date, "%Y-%m-%d", strict=True),
                pl.col("open").cast(pl.Float64),
                pl.col("high").cast(pl.Float64),
                pl.col("low").cast(pl.Float64),
                pl.col("close").cast(pl.Float64),
                pl.col("adj_close").cast(pl.Float64),
                pl.col("volume").cast(pl.Int64),
            ]
        )

        OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(OUT_PARQUET, compression="snappy")

    size_kb = OUT_PARQUET.stat().st_size / 1024
    content_hash = xxhash.xxh64(OUT_PARQUET.read_bytes()).hexdigest()
    schema = {col: str(dtype) for col, dtype in df.schema.items()}

    # Sidecar JSON consumed by the v1 migration. The migration container
    # only has stdlib + sqlalchemy/alembic — no polars, no xxhash — so it
    # reads the sidecar instead of recomputing from parquet bytes. Both
    # files come from this same fetch and ship together; drift between
    # them is caught by apps/api/tests/test_bundled_dataset.py.
    meta = {
        "ticker": TICKER,
        "content_hash_hex": content_hash,
        "schema": schema,
        "rows": df.height,
        "date_min": str(df["date"].min()),
        "date_max": str(df["date"].max()),
    }
    META_PATH.write_text(json.dumps(meta, indent=2) + "\n")

    print(
        f"\nWrote {OUT_PARQUET} ({df.height:,} rows, {size_kb:.1f} KB)\n"
        f"  date range: {meta['date_min']} → {meta['date_max']}\n"
        f"  xxh64 content hash: {content_hash}\n"
        f"  schema: {json.dumps(schema)}\n"
        f"Wrote sidecar metadata at {META_PATH}\n"
    )

    # Update / write provenance sidecar
    provenance = (
        f"# Bundled dataset: {OUT_PARQUET.name}\n\n"
        f"- **Ticker:** {TICKER}\n"
        f"- **Source:** [{KAGGLE_DATASET}](https://www.kaggle.com/datasets/{KAGGLE_DATASET})\n"
        f"- **Source file:** `{KAGGLE_FILE_PATH}`\n"
        f"- **Source license:** CC0 Public Domain — no restrictions on redistribution,\n"
        f"  modification, or commercial use. Verified at the dataset page on the\n"
        f"  fetch date below.\n"
        f"- **Fetched on:** 2026-04-25 (regenerate by running `uv run python "
        f"scripts/refresh_aapl_data.py`)\n"
        f"- **Date range in this snapshot:** {df['date'].min()} → {df['date'].max()}\n"
        f"- **Rows:** {df.height:,}\n"
        f"- **xxh64 content hash:** `{content_hash}`\n"
        f"- **Schema (polars dtype names):** `{json.dumps(schema)}`\n"
        f"\n"
        f"Both the content hash and the schema are guarded by\n"
        f"`apps/api/tests/test_bundled_dataset.py` against the v1 migration's seed\n"
        f"INSERT — drift between the parquet and the registered metadata fails the\n"
        f"test fast.\n"
    )
    PROVENANCE_PATH.write_text(provenance)
    print(f"Wrote provenance sidecar at {PROVENANCE_PATH}")
    print(
        "\nNo manual paste needed: the v1 migration reads the sidecar JSON at "
        "upgrade time. Both files (parquet + meta.json) ship together as a "
        "coherent unit; drift is caught by apps/api/tests/test_bundled_dataset.py."
    )


if __name__ == "__main__":
    main()
