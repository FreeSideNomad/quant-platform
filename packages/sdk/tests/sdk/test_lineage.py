"""Unit tests for the lineage-writer module."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import psycopg2
import psycopg2.extras
import pytest
import xxhash

from quantplatform.sdk.lineage import compute_content_hash, record_read


def test_compute_content_hash_is_deterministic_xxh64() -> None:
    data = b"hello, world\n"
    expected = xxhash.xxh64(data).digest()
    assert compute_content_hash(data) == expected
    assert len(compute_content_hash(data)) == 8  # xxh64 = 8-byte digest


def test_compute_content_hash_distinguishes_payloads() -> None:
    assert compute_content_hash(b"a") != compute_content_hash(b"b")


@pytest.fixture
def strategy_and_run(db_url_env: str) -> tuple[str, str]:
    """Seed a strategies row + a runs row; return (strategy_id, run_id)."""
    conn = psycopg2.connect(db_url_env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO strategies (name, entry_point, thresholds) "
                "VALUES (%s, %s, '{}'::jsonb) RETURNING id",
                (f"t-{uuid4().hex[:8]}", "fake:main"),
            )
            sid = str(cur.fetchone()[0])
            cur.execute(
                "INSERT INTO runs (strategy_id, as_of, status) "
                "VALUES (%s, %s, 'running') RETURNING id",
                (sid, date(2024, 12, 1)),
            )
            rid = str(cur.fetchone()[0])
        conn.commit()
    finally:
        conn.close()
    return sid, rid


def test_record_read_inserts_lineage_row_and_emits_dataread(
    db_url_env: str, strategy_and_run: tuple[str, str]
) -> None:
    _, rid = strategy_and_run

    # Use the seed dataset_version from migration 0002
    conn = psycopg2.connect(db_url_env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT dv.id::text FROM dataset_versions dv "
                "JOIN datasets d ON d.id = dv.dataset_id "
                "WHERE d.name = 'ohlcv-spy-daily-synthetic' AND dv.version_tag = 'v1'"
            )
            dv_id = cur.fetchone()[0]
    finally:
        conn.close()

    ch = compute_content_hash(b"test-bytes")
    record_read(
        run_id=rid,
        dataset_version_id=dv_id,
        as_of=date(2024, 12, 1),
        filter_predicates={"ticker": "SPY"},
        content_hash=ch,
        rows_returned=2500,
    )

    conn = psycopg2.connect(db_url_env)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM lineage_reads WHERE run_id = %s", (rid,)
            )
            rows = cur.fetchall()
            assert len(rows) == 1
            assert bytes(rows[0]["content_hash"]) == ch
            assert rows[0]["rows_returned"] == 2500

            cur.execute(
                "SELECT event_type, payload FROM events WHERE run_id = %s", (rid,)
            )
            events = cur.fetchall()
            event_types = [e["event_type"] for e in events]
            assert "DataRead" in event_types
            dread = [e for e in events if e["event_type"] == "DataRead"][0]
            assert dread["payload"]["content_hash"] == ch.hex()
            assert dread["payload"]["rows_returned"] == 2500
    finally:
        conn.close()
