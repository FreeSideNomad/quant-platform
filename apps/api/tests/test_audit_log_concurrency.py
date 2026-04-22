# apps/api/tests/test_audit_log_concurrency.py
"""Concurrent appends must preserve the chain — no two rows share prev_hash."""

import asyncio

import pytest
from sqlalchemy import text

from app.audit.log import append_audit_event, verify_audit_chain
from app.infra.db import session_scope


@pytest.mark.integration
async def test_concurrent_appends_preserve_chain():
    """20 concurrent appenders, each writing 5 events, produce a valid chain of 100."""

    async def appender(worker_id: int) -> None:
        for i in range(5):
            async with session_scope() as session:
                await append_audit_event(
                    session,
                    actor=f"worker-{worker_id}",
                    event_type="StressTest",
                    aggregate_type="T",
                    aggregate_id=f"w{worker_id}-i{i}",
                    payload={"worker": worker_id, "i": i},
                )

    await asyncio.gather(*(appender(w) for w in range(20)))

    async with session_scope() as session:
        check = await verify_audit_chain(session)
        rows = (
            await session.execute(text("SELECT count(*), count(distinct prev_hash) FROM audit_log"))
        ).one()

    assert check.ok is True, f"Chain broken at {check.first_break}: {check.detail}"
    assert check.checked == 100
    assert rows[0] == 100  # 100 total rows
    assert rows[1] == 99   # genesis row's prev_hash is NULL; 99 unique non-NULL prev_hash values
