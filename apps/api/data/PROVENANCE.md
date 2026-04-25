# Bundled dataset: aapl_daily.parquet

- **Ticker:** AAPL
- **Source:** [jacksoncrow/stock-market-dataset](https://www.kaggle.com/datasets/jacksoncrow/stock-market-dataset)
- **Source file:** `stocks/AAPL.csv`
- **Source license:** CC0 Public Domain — no restrictions on redistribution,
  modification, or commercial use. Verified at the dataset page on the
  fetch date below.
- **Fetched on:** 2026-04-25 (regenerate by running `uv run python scripts/refresh_aapl_data.py`)
- **Date range in this snapshot:** 1980-12-12 → 2020-04-01
- **Rows:** 9,909
- **xxh64 content hash:** `355289745a4e6068`
- **Schema (polars dtype names):** `{"date": "Date", "open": "Float64", "high": "Float64", "low": "Float64", "close": "Float64", "adj_close": "Float64", "volume": "Int64"}`

Both the content hash and the schema are guarded by
`apps/api/tests/test_bundled_dataset.py` against the v1 migration's seed
INSERT — drift between the parquet and the registered metadata fails the
test fast.
