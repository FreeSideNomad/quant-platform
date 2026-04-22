import pytest
from sqlalchemy import text

from app.infra.db import session_scope


@pytest.fixture(autouse=True)
async def _clean_strategies():
    """Truncate strategies before each test to avoid cross-test leakage."""
    async with session_scope() as session:
        await session.execute(text("TRUNCATE strategies"))
        await session.commit()
    yield


@pytest.mark.integration
async def test_strategies_table_exists_with_expected_columns():
    async with session_scope() as session:
        result = await session.execute(
            text(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'strategies'
                ORDER BY ordinal_position
                """
            )
        )
        columns = {row[0]: row[1] for row in result.fetchall()}

    assert "id" in columns
    assert "family" in columns
    assert "spec" in columns
    assert columns["spec"] == "jsonb"
    assert "registered_at" in columns
    assert "registered_by" in columns
    assert "spec_hash" in columns


@pytest.mark.integration
async def test_strategies_unique_on_family_spec_hash():
    async with session_scope() as session:
        await session.execute(
            text(
                """
                INSERT INTO strategies (id, family, spec, registered_by, spec_hash)
                VALUES ('id1', 'us_equity_long_short_alpha158', '{}'::jsonb, 'test', 'h1')
                """
            )
        )
        await session.commit()

    with pytest.raises(Exception, match="duplicate key"):
        async with session_scope() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO strategies (id, family, spec, registered_by, spec_hash)
                    VALUES ('id2', 'us_equity_long_short_alpha158', '{}'::jsonb, 'test', 'h1')
                    """
                )
            )
            await session.commit()
