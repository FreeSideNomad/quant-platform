import pytest
from sqlalchemy import text

from app.infra.db import session_scope


@pytest.mark.integration
async def test_walk_forward_folds_table_columns_in_order():
    async with session_scope() as session:
        result = await session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'walk_forward_folds'
                ORDER BY ordinal_position
                """
            )
        )
        columns = [row[0] for row in result.fetchall()]

    assert columns == [
        "id",
        "training_run_id",
        "fold_index",
        "train_start",
        "train_end",
        "test_start",
        "test_end",
        "in_sample_ic",
        "out_of_sample_ic",
        "out_of_sample_sharpe",
        "metrics",
        "created_at",
    ]
