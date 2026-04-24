# packages/sdk/tests/sdk/test_audit_log.py
"""Ported from apps/api/tests/test_audit_log.py (MVP-A archive).

Adaptations:
- Async AsyncSession + session_scope → sync emit_event / verify_chain.
- Table audit_log → events; row_hash → this_hash (BYTEA); id is UUID.
- actor/aggregate_type/aggregate_id removed from signature — encode in payload.
- prev_hash genesis is b'' (NOT NULL) instead of NULL.
- verify_audit_chain → verify_chain; AuditChainCheck → ChainCheck.
"""
from __future__ import annotations

import psycopg2
import psycopg2.extras
import pytest

from quantplatform.sdk.audit import ChainCheck, emit_event, verify_chain


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_event(db_url: str, event_id: str) -> dict:
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT prev_hash, this_hash FROM events WHERE id = %(id)s::uuid",
                {"id": event_id},
            )
            row = cur.fetchone()
            return dict(row)
    finally:
        conn.close()


def _truncate_events(db_url: str) -> None:
    """Truncate events between tests so each test starts fresh."""
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE events RESTART IDENTITY CASCADE")
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_first_event_has_empty_prev_hash(db_url_env: str) -> None:
    _truncate_events(db_url_env)
    event_id = emit_event(
        run_id=None,
        event_type="StrategyRegistered",
        payload={"family": "csi300_long_short_alpha158"},
    )

    row = _fetch_event(db_url_env, event_id)
    # Genesis row: prev_hash must be b'' (empty bytes, satisfies NOT NULL).
    assert row["prev_hash"].tobytes() == b""
    assert row["this_hash"] is not None
    # SHA-256 digest is 32 bytes.
    assert len(row["this_hash"].tobytes()) == 32


@pytest.mark.integration
def test_subsequent_event_chains_to_prior(db_url_env: str) -> None:
    _truncate_events(db_url_env)

    first_id = emit_event(
        run_id=None,
        event_type="StrategyRegistered",
        payload={"i": 1},
    )

    first_row = _fetch_event(db_url_env, first_id)
    first_this_hash = first_row["this_hash"].tobytes()

    second_id = emit_event(
        run_id=None,
        event_type="ModelPromoted",
        payload={"i": 2},
    )

    second_row = _fetch_event(db_url_env, second_id)
    assert second_row["prev_hash"].tobytes() == first_this_hash
    assert second_row["this_hash"].tobytes() != first_this_hash


@pytest.mark.integration
def test_verify_chain_passes_when_intact(db_url_env: str) -> None:
    _truncate_events(db_url_env)
    for i in range(5):
        emit_event(run_id=None, event_type="X", payload={"i": i})

    result: ChainCheck = verify_chain()
    assert result.ok is True
    assert result.checked == 5
    assert result.first_break is None


@pytest.mark.integration
def test_verify_chain_detects_tampered_payload(db_url_env: str) -> None:
    """If a stored row's payload is tampered with (bypassing the immutability
    check via session_replication_role=replica), verify_chain reports the break
    at the tampered row's id."""
    _truncate_events(db_url_env)

    ids = []
    for i in range(3):
        ids.append(emit_event(run_id=None, event_type="X", payload={"i": i}))

    # Tamper the middle row's payload, bypassing any trigger via session_replication_role.
    conn = psycopg2.connect(db_url_env)
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("SET LOCAL session_replication_role = replica")
                cur.execute(
                    "UPDATE events SET payload = '{\"tampered\": true}'::jsonb WHERE id = %(id)s::uuid",
                    {"id": ids[1]},
                )
            except Exception as e:  # pragma: no cover
                pytest.skip(f"Cannot bypass trigger in this environment: {e}")
        conn.commit()
    finally:
        conn.close()

    result: ChainCheck = verify_chain()
    assert result.ok is False
    assert result.first_break == ids[1]
    assert "this_hash mismatch" in (result.detail or "")


@pytest.mark.integration
def test_verify_chain_handles_unicode_and_nested_payloads(db_url_env: str) -> None:
    """Roundtrip through JSONB -> text -> json.loads -> json.dumps must preserve
    the canonical bytes used at insert time, for Unicode strings, nested
    objects, integers, floats, booleans, and nulls."""
    _truncate_events(db_url_env)

    payloads = [
        {"unicode": "日本語のテスト", "emoji": None},
        {"nested": {"a": [1, 2, 3], "b": {"c": True, "d": False}}},
        {"numbers": {"int": 42, "float": 3.14159, "big_int": 10**15, "zero": 0}},
        {"empty_dict": {}, "empty_list": []},
        {"null": None, "bool_true": True, "bool_false": False},
    ]

    for i, p in enumerate(payloads):
        emit_event(run_id=None, event_type="X", payload=p)

    result: ChainCheck = verify_chain()
    assert result.ok is True, f"Chain broken at id={result.first_break}: {result.detail}"
    assert result.checked == len(payloads)
