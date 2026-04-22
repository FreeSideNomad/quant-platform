import pytest
from sqlalchemy import text

from app.infra.db import session_scope


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
    """UPDATE on audit_log is rejected by the append-only trigger.

    INSERT and UPDATE happen in the SAME transaction with no interim commit.
    When the UPDATE fires the trigger and raises, session_scope catches the
    exception, rolls back the whole transaction, and the seed row is never
    persisted — zero rows leak.
    """
    with pytest.raises(Exception, match="audit_log is append-only"):
        async with session_scope() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO audit_log (actor, event_type, aggregate_type, aggregate_id, payload, row_hash)
                    VALUES ('test', 'TestEvent', 'Test', 'a1', '{}'::jsonb, 'test_hash_placeholder')
                    """
                )
            )
            # No commit — INSERT and UPDATE share the same transaction.
            # The trigger fires on the UPDATE statement; when it raises,
            # session_scope rolls back, and the INSERT is also undone.
            await session.execute(
                text("UPDATE audit_log SET actor = 'attacker' WHERE actor = 'test'")
            )
            await session.commit()

    # Sanity check: the seed row must not have survived the rollback.
    async with session_scope() as session:
        count = (
            await session.execute(
                text("SELECT count(*) FROM audit_log WHERE actor = 'test'")
            )
        ).scalar()
    assert count == 0, f"Expected 0 rows after rollback, found {count}"


@pytest.mark.integration
async def test_audit_log_rejects_delete():
    """DELETE on audit_log is rejected by the append-only trigger.

    The trigger is FOR EACH ROW, so a row must exist for it to fire.
    INSERT and DELETE share the same transaction; when the trigger raises
    on the DELETE, session_scope rolls the whole transaction back — no leak.
    """
    with pytest.raises(Exception, match="audit_log is append-only"):
        async with session_scope() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO audit_log (actor, event_type, aggregate_type, aggregate_id, payload, row_hash)
                    VALUES ('test_delete', 'TestEvent', 'Test', 'b1', '{}'::jsonb, 'test_hash_del')
                    """
                )
            )
            # No commit — INSERT and DELETE share the same transaction.
            # The trigger fires on DELETE; when it raises, the INSERT also rolls back.
            await session.execute(text("DELETE FROM audit_log WHERE actor = 'test_delete'"))
            await session.commit()
