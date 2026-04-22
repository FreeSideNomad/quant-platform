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
        await session.commit()

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
        await session.commit()

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
        await session.commit()

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
        await session.commit()

    async with session_scope() as session:
        result = await verify_audit_chain(session)

    assert result.ok is True
    assert result.checked == 5
    assert result.first_break is None
