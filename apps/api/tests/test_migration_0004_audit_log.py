import pytest
from sqlalchemy import text

from app.infra.db import dispose_engine, session_scope


@pytest.fixture(autouse=True)
async def reset_db_engine():
    """Dispose the global engine after each test so the next test gets a fresh pool."""
    yield
    await dispose_engine()


@pytest.mark.integration
async def test_audit_log_table_exists():
    """After migration 0005, audit_log table exists with the expected columns."""
    async with session_scope() as session:
        result = await session.execute(
            text(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'audit_log'
                ORDER BY ordinal_position
                """
            )
        )
        columns = {row[0]: (row[1], row[2]) for row in result.fetchall()}

    assert "id" in columns
    assert "occurred_at" in columns
    assert "actor" in columns
    assert "event_type" in columns
    assert "aggregate_type" in columns
    assert "aggregate_id" in columns
    assert "payload" in columns
    assert columns["payload"][0] == "jsonb"
    assert "prev_hash" in columns
    assert "row_hash" in columns
    assert columns["row_hash"][1] == "NO"  # NOT NULL


@pytest.mark.integration
async def test_audit_log_rejects_update():
    """UPDATE on audit_log is rejected by a trigger."""
    async with session_scope() as session:
        await session.execute(
            text(
                """
                INSERT INTO audit_log (actor, event_type, aggregate_type, aggregate_id, payload, row_hash)
                VALUES ('test', 'TestEvent', 'Test', 'a1', '{}'::jsonb, 'test_hash_placeholder')
                """
            )
        )
        await session.commit()

    with pytest.raises(Exception, match="audit_log is append-only"):
        async with session_scope() as session:
            await session.execute(
                text("UPDATE audit_log SET actor = 'attacker' WHERE actor = 'test'")
            )
            await session.commit()


@pytest.mark.integration
async def test_audit_log_rejects_delete():
    """DELETE on audit_log is rejected by a trigger."""
    with pytest.raises(Exception, match="audit_log is append-only"):
        async with session_scope() as session:
            await session.execute(text("DELETE FROM audit_log"))
            await session.commit()
