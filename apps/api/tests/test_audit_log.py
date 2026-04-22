# apps/api/tests/test_audit_log.py
import pytest
from sqlalchemy import text

from app.audit.log import append_audit_event, verify_audit_chain
from app.infra.db import session_scope


@pytest.mark.integration
async def test_first_event_has_null_prev_hash():
    async with session_scope() as session:
        event_id = await append_audit_event(
            session,
            actor="test",
            event_type="StrategyRegistered",
            aggregate_type="Strategy",
            aggregate_id="csi300_alpha158_v1",
            payload={"family": "csi300_long_short_alpha158"},
        )

        row = (
            await session.execute(
                text("SELECT prev_hash, row_hash FROM audit_log WHERE id = :id"),
                {"id": event_id},
            )
        ).one()

    assert row.prev_hash is None
    assert row.row_hash is not None
    assert len(row.row_hash) == 64  # SHA-256 hex digest


@pytest.mark.integration
async def test_subsequent_event_chains_to_prior():
    async with session_scope() as session:
        first_id = await append_audit_event(
            session,
            actor="test",
            event_type="StrategyRegistered",
            aggregate_type="Strategy",
            aggregate_id="s1",
            payload={"i": 1},
        )

    async with session_scope() as session:
        first_hash = (
            await session.execute(
                text("SELECT row_hash FROM audit_log WHERE id = :id"),
                {"id": first_id},
            )
        ).scalar_one()

        second_id = await append_audit_event(
            session,
            actor="test",
            event_type="ModelPromoted",
            aggregate_type="Model",
            aggregate_id="m1",
            payload={"i": 2},
        )

        second_row = (
            await session.execute(
                text("SELECT prev_hash, row_hash FROM audit_log WHERE id = :id"),
                {"id": second_id},
            )
        ).one()

    assert second_row.prev_hash == first_hash
    assert second_row.row_hash != first_hash


@pytest.mark.integration
async def test_verify_audit_chain_passes_when_intact():
    async with session_scope() as session:
        for i in range(5):
            await append_audit_event(
                session,
                actor="test",
                event_type="X",
                aggregate_type="Y",
                aggregate_id=f"id{i}",
                payload={"i": i},
            )

    async with session_scope() as session:
        result = await verify_audit_chain(session)

    assert result.ok is True
    assert result.checked == 5
    assert result.first_break is None


@pytest.mark.integration
async def test_verify_audit_chain_detects_tampered_payload():
    """If a stored row's payload is tampered with (bypassing the immutability
    trigger via session_replication_role=replica), verify_audit_chain reports
    the break at the tampered row's id."""
    async with session_scope() as session:
        ids = []
        for i in range(3):
            ids.append(
                await append_audit_event(
                    session,
                    actor="test",
                    event_type="X",
                    aggregate_type="Y",
                    aggregate_id=f"id{i}",
                    payload={"i": i},
                )
            )

    # Tamper the middle row's payload, bypassing the trigger via session_replication_role.
    # This privilege normally requires superuser; in our local docker-compose Postgres
    # the `quant` role has it. If this fails in your environment, the test is
    # skipped — the verify path is the production concern, the tamper is just to set up.
    async with session_scope() as session:
        try:
            await session.execute(text("SET LOCAL session_replication_role = replica"))
            await session.execute(
                text("UPDATE audit_log SET payload = '{\"tampered\": true}'::jsonb WHERE id = :id"),
                {"id": ids[1]},
            )
        except Exception as e:  # pragma: no cover
            pytest.skip(f"Cannot bypass trigger in this environment: {e}")

    async with session_scope() as session:
        result = await verify_audit_chain(session)

    assert result.ok is False
    assert result.first_break == ids[1]
    assert "row_hash mismatch" in (result.detail or "")


@pytest.mark.integration
async def test_verify_audit_chain_handles_unicode_and_nested_payloads():
    """Roundtrip through JSONB → text → json.loads → json.dumps must preserve
    the canonical bytes used at insert time, for Unicode strings, nested
    objects, integers, floats, booleans, and nulls."""
    payloads = [
        {"unicode": "日本語のテスト", "emoji": None},
        {"nested": {"a": [1, 2, 3], "b": {"c": True, "d": False}}},
        {"numbers": {"int": 42, "float": 3.14159, "big_int": 10**15, "zero": 0}},
        {"empty_dict": {}, "empty_list": []},
        {"null": None, "bool_true": True, "bool_false": False},
    ]

    async with session_scope() as session:
        for i, p in enumerate(payloads):
            await append_audit_event(
                session,
                actor="test",
                event_type="X",
                aggregate_type="Y",
                aggregate_id=f"p{i}",
                payload=p,
            )

    async with session_scope() as session:
        result = await verify_audit_chain(session)

    assert result.ok is True, f"Chain broken at id={result.first_break}: {result.detail}"
    assert result.checked == len(payloads)
