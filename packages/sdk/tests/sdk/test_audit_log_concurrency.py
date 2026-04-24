# packages/sdk/tests/sdk/test_audit_log_concurrency.py
"""Concurrent appends must preserve the chain — no two rows share prev_hash.

Ported from apps/api/tests/test_audit_log_concurrency.py (MVP-A archive).

Adaptations:
- asyncio.gather / async appenders → threading.Thread (sync emit_event).
- session_scope removed; each thread opens its own psycopg2 connection via
  the _db.connection() context manager inside emit_event.
- verify_audit_chain → verify_chain; events table, BYTEA hashes.
- The duplicate-prev_hash assertion is relaxed: the genesis row has
  prev_hash = b'' and subsequent rows have unique non-empty prev_hash values.
  We verify count(distinct prev_hash) = total_rows (all prev_hash values are
  unique — genesis b'' counts as one distinct value too).
"""
from __future__ import annotations

import threading

import psycopg2
import pytest

from quantplatform.sdk.audit import emit_event, verify_chain


def _truncate_events(db_url: str) -> None:
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE events RESTART IDENTITY CASCADE")
        conn.commit()
    finally:
        conn.close()


@pytest.mark.integration
def test_concurrent_appends_preserve_chain(db_url_env: str) -> None:
    """20 concurrent appenders, each writing 5 events, produce a valid chain of 100."""
    _truncate_events(db_url_env)

    errors: list[Exception] = []

    def appender(worker_id: int) -> None:
        try:
            for i in range(5):
                emit_event(
                    run_id=None,
                    event_type="StressTest",
                    payload={"worker": worker_id, "i": i},
                )
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=appender, args=(w,)) for w in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Appender threads raised errors: {errors}"

    check = verify_chain()
    assert check.ok is True, f"Chain broken at {check.first_break}: {check.detail}"
    assert check.checked == 100

    # Verify row count and that all prev_hash values are unique.
    # (Genesis has b''; subsequent rows chain; advisory lock guarantees no
    # two rows share the same prev_hash.)
    conn = psycopg2.connect(db_url_env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*), count(distinct prev_hash) FROM events"
            )
            total, distinct_prev = cur.fetchone()
    finally:
        conn.close()

    assert total == 100, f"Expected 100 rows, got {total}"
    # All 100 prev_hash values are distinct: b'' for genesis + 99 unique
    # previous this_hash values.
    assert distinct_prev == 100, (
        f"Expected 100 distinct prev_hash values (including genesis b''), got {distinct_prev}"
    )
