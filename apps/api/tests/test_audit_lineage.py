# apps/api/tests/test_audit_lineage.py
import uuid

import pytest
from sqlalchemy import text

from app.infra.db import session_scope


@pytest.fixture(autouse=True)
async def _seed_lineage():
    async with session_scope() as session:
        # Clear any rows from other tests so LIMIT 1 picks our row.
        await session.execute(text("DELETE FROM inference_log"))
        # inference_log has: id (text), model_id (text), model_version (text),
        # instrument (text), as_of_date (date), feature_hash (text),
        # prediction (double precision), latency_ms (int)
        inf_id = str(uuid.uuid4())
        await session.execute(
            text(
                """
                INSERT INTO inference_log
                    (id, model_id, model_version, instrument, as_of_date,
                     feature_hash, prediction, latency_ms)
                VALUES
                    (:id, 'qlib-lgbm', 'v1', 'AAPL', '2024-01-01',
                     'abc123', 0.42, 45)
                """
            ),
            {"id": inf_id},
        )
        await session.commit()
    yield


@pytest.mark.integration
async def test_lineage_returns_inference_model_training_chain(test_client):
    async with session_scope() as session:
        inf_id = (
            await session.execute(text("SELECT id FROM inference_log LIMIT 1"))
        ).scalar_one()

    response = await test_client.get(f"/api/audit/inference/{inf_id}/lineage")
    assert response.status_code == 200
    body = response.json()

    assert "inference" in body
    assert "model_version" in body
    assert "training_run" in body
    assert "audit_events" in body
    assert body["inference"]["model_id"] == "qlib-lgbm"
    assert body["inference"]["model_version"] == "v1"
    assert isinstance(body["audit_events"], list)


@pytest.mark.integration
async def test_lineage_404_for_unknown_inference_id(test_client):
    response = await test_client.get(
        "/api/audit/inference/00000000-0000-0000-0000-000000000000/lineage"
    )
    assert response.status_code == 404
