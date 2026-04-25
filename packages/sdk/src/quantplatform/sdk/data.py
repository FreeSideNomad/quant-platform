"""sdk.data.* — the ONLY sanctioned data access path.

Reads are lineage-tracked: every call writes to lineage_reads and
emits a DataRead audit event. Raw file I/O outside this module will
be flagged by pq check (M4+).
"""
from __future__ import annotations

import io
from datetime import date

import boto3
import polars as pl

from quantplatform.sdk._config import get_settings
from quantplatform.sdk._db import fetch_one
from quantplatform.sdk.lineage import compute_content_hash, record_read
from quantplatform.sdk.run import current_run_id


_DATASET_NAME = "ohlcv-aapl-daily"
_DATASET_VERSION = "v1"
_BUNDLED_TICKER = "AAPL"


def ohlcv(*, ticker: str, as_of: date | str | None = None) -> pl.DataFrame:
    """Load daily OHLCV bars.

    MVP: only the bundled AAPL daily dataset is registered out of the box
    (real historical data sourced from a CC0 Public Domain Kaggle
    snapshot — see apps/api/data/PROVENANCE.md for source + fetch date).
    Users register their own data with `pq data register` (M4+).

    `as_of` filters by `_knowable_at` if the bi-temporal columns exist
    on the parquet — the bundled v1 data has no such columns so `as_of`
    is recorded in lineage but does not filter rows.

    Must be called inside a `run.start(...)` context.
    """
    if ticker.upper() != _BUNDLED_TICKER:
        raise ValueError(
            f"only {_BUNDLED_TICKER} is bundled in MVP; got ticker={ticker!r}. "
            f"Register custom data with `pq data register` (M4+)."
        )

    # Must be inside a run context
    run_id = current_run_id()

    # Normalize as_of
    as_of_date: date | None
    if isinstance(as_of, str):
        as_of_date = date.fromisoformat(as_of)
    else:
        as_of_date = as_of

    # Resolve the dataset version
    dv = fetch_one(
        """
        SELECT dv.id::text AS id, dv.storage_uri AS storage_uri
        FROM dataset_versions dv
        JOIN datasets d ON d.id = dv.dataset_id
        WHERE d.name = %(name)s AND dv.version_tag = %(tag)s
        """,
        name=_DATASET_NAME,
        tag=_DATASET_VERSION,
    )
    if dv is None:
        raise RuntimeError(
            f"{_DATASET_NAME}/{_DATASET_VERSION} not registered; "
            f"is the compose stack bootstrapped (v1 migration run)?"
        )

    # Download the raw bytes from MinIO (via boto3)
    settings = get_settings()
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name="us-east-1",
    )
    uri = dv.storage_uri
    assert uri.startswith("s3://"), f"unexpected storage_uri: {uri!r}"
    bucket, key = uri.removeprefix("s3://").split("/", 1)
    response = s3.get_object(Bucket=bucket, Key=key)
    raw_bytes = response["Body"].read()

    # Compute content hash and load the DataFrame
    ch = compute_content_hash(raw_bytes)
    df = pl.read_parquet(io.BytesIO(raw_bytes))

    # Apply as_of filter if bi-temporal columns exist (MVP: they don't)
    filter_predicates: dict = {"ticker": ticker}
    if as_of_date is not None:
        filter_predicates["as_of"] = as_of_date.isoformat()
        if "_knowable_at" in df.columns:
            df = df.filter(pl.col("_knowable_at") <= as_of_date)

    # Record the read: lineage_reads row + DataRead audit event
    record_read(
        run_id=run_id,
        dataset_version_id=dv.id,
        as_of=as_of_date,
        filter_predicates=filter_predicates,
        content_hash=ch,
        rows_returned=df.height,
    )
    return df
