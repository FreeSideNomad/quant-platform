"""Unit tests for sdk.data.ohlcv (boto3 mocked; DB real)."""
from __future__ import annotations

from datetime import date
from io import BytesIO
from unittest.mock import MagicMock, patch
from uuid import uuid4

import polars as pl
import psycopg2
import psycopg2.extras
import pytest

from quantplatform.sdk import data, run
from quantplatform.sdk.lineage import compute_content_hash


@pytest.fixture
def strategy_id(db_url_env: str) -> str:
    conn = psycopg2.connect(db_url_env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO strategies (name, entry_point, thresholds) "
                "VALUES (%s, %s, '{}'::jsonb) RETURNING id",
                (f"t-{uuid4().hex[:8]}", "fake:main"),
            )
            sid = str(cur.fetchone()[0])
        conn.commit()
    finally:
        conn.close()
    return sid


def _make_fake_parquet_bytes() -> bytes:
    df = pl.DataFrame({
        "date": [date(2024, 1, 1), date(2024, 1, 2)],
        "open": [100.0, 101.0],
        "high": [101.0, 102.0],
        "low": [99.0, 100.0],
        "close": [100.5, 101.5],
        "adj_close": [100.5, 101.5],
        "volume": [1_000_000, 1_100_000],
    })
    buf = BytesIO()
    df.write_parquet(buf)
    return buf.getvalue()


def test_ohlcv_outside_run_raises(db_url_env: str) -> None:
    with pytest.raises(RuntimeError, match="outside of a run"):
        data.ohlcv(ticker="SPY")


def test_ohlcv_rejects_non_spy_ticker(db_url_env: str, strategy_id: str) -> None:
    with run.start(strategy_id=strategy_id, as_of="2024-12-01"):
        with pytest.raises(ValueError, match="only SPY"):
            data.ohlcv(ticker="AAPL")


def test_ohlcv_returns_df_and_writes_lineage(db_url_env: str, strategy_id: str) -> None:
    raw = _make_fake_parquet_bytes()
    expected_hash = compute_content_hash(raw)

    # Mock boto3.client to return a client whose get_object returns raw bytes
    fake_s3 = MagicMock()
    fake_s3.get_object.return_value = {"Body": BytesIO(raw)}
    with patch("quantplatform.sdk.data.boto3.client", return_value=fake_s3):
        with run.start(strategy_id=strategy_id, as_of="2024-12-01") as r:
            df = data.ohlcv(ticker="SPY", as_of="2024-12-01")

    assert df.height == 2
    assert set(df.columns) >= {"date", "open", "high", "low", "close", "volume"}

    # Verify lineage row was written
    conn = psycopg2.connect(db_url_env)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT content_hash, rows_returned, filter_predicates "
                "FROM lineage_reads WHERE run_id = %s",
                (r.id,),
            )
            rows = cur.fetchall()
            assert len(rows) == 1
            assert bytes(rows[0]["content_hash"]) == expected_hash
            assert rows[0]["rows_returned"] == 2
            assert rows[0]["filter_predicates"]["ticker"] == "SPY"
    finally:
        conn.close()
