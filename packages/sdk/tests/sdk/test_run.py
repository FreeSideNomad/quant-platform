"""Unit tests for sdk.run — run lifecycle + audit chain integration."""
from __future__ import annotations

from uuid import uuid4

import psycopg2
import psycopg2.extras
import pytest

from quantplatform.sdk import run


@pytest.fixture
def strategy_row(db_url_env: str) -> str:
    """Insert a dummy strategies row and return its UUID."""
    conn = psycopg2.connect(db_url_env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO strategies (name, entry_point, thresholds)
                VALUES (%s, %s, '{}'::jsonb)
                RETURNING id
                """,
                (f"t-{uuid4().hex[:8]}", "fake.entry:main"),
            )
            sid = str(cur.fetchone()[0])
        conn.commit()
    finally:
        conn.close()
    return sid


def _fetch_events(db_url: str, run_id: str) -> list[dict]:
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT event_type, payload, prev_hash, this_hash "
                "FROM events WHERE run_id = %s ORDER BY created_at",
                (run_id,),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _fetch_run(db_url: str, run_id: str) -> dict:
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM runs WHERE id = %s", (run_id,))
            return dict(cur.fetchone())
    finally:
        conn.close()


def test_run_clean_exit_marks_succeeded_and_emits_runstarted_runfinished(
    db_url_env: str, strategy_row: str
) -> None:
    with run.start(strategy_id=strategy_row, as_of="2024-12-01") as r:
        assert r.status == "running"
        assert run.current_run_id() == r.id

    row = _fetch_run(db_url_env, r.id)
    assert row["status"] == "succeeded"
    assert row["finished_at"] is not None

    events = _fetch_events(db_url_env, r.id)
    types = [e["event_type"] for e in events]
    assert types == ["RunStarted", "RunFinished"]


def test_run_exception_marks_failed_and_emits_runfailed(
    db_url_env: str, strategy_row: str
) -> None:
    with pytest.raises(ValueError, match="boom"):
        with run.start(strategy_id=strategy_row, as_of="2024-12-01") as r:
            raise ValueError("boom")

    row = _fetch_run(db_url_env, r.id)
    assert row["status"] == "failed"
    assert row["finished_at"] is not None

    events = _fetch_events(db_url_env, r.id)
    types = [e["event_type"] for e in events]
    assert types == ["RunStarted", "RunFailed"]
    failed = [e for e in events if e["event_type"] == "RunFailed"][0]
    assert failed["payload"]["exception_type"] == "ValueError"
    assert failed["payload"]["exception_message"] == "boom"


def test_current_run_id_raises_outside_run_context(db_url_env: str) -> None:
    with pytest.raises(RuntimeError, match="outside of a run.start"):
        run.current_run_id()


def test_nested_run_start_is_forbidden(db_url_env: str, strategy_row: str) -> None:
    with run.start(strategy_id=strategy_row, as_of="2024-12-01") as r1:
        with pytest.raises(RuntimeError, match="nested run.start"):
            with run.start(strategy_id=strategy_row, as_of="2024-12-02"):
                pass


def test_run_log_emits_runlog_event(db_url_env: str, strategy_row: str) -> None:
    with run.start(strategy_id=strategy_row, as_of="2024-12-01") as r:
        r.log("fit starting", ticker="SPY", rows=2500)

    events = _fetch_events(db_url_env, r.id)
    types = [e["event_type"] for e in events]
    assert "RunLog" in types
    log_evt = [e for e in events if e["event_type"] == "RunLog"][0]
    assert log_evt["payload"]["message"] == "fit starting"
    assert log_evt["payload"]["ticker"] == "SPY"
    assert log_evt["payload"]["rows"] == 2500


def test_run_start_rejects_unknown_strategy(db_url_env: str) -> None:
    with pytest.raises(ValueError, match="not found"):
        with run.start(strategy_id="00000000-0000-0000-0000-000000000000",
                       as_of="2024-12-01"):
            pass
