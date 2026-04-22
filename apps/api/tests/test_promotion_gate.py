"""Integration tests for PATCH /api/models/{model_id}/versions/{version}/promote."""

import pytest
from sqlalchemy import text

from app.infra.db import session_scope

# Fixed IDs for test isolation
_TEST_RUN_IDS = ["test-run-pgate-1", "test-run-pgate-2", "test-run-pgate-3"]
_TEST_VERSION_IDS = ["test-mv-pgate-1", "test-mv-pgate-2", "test-mv-pgate-3"]
_TEST_VERSIONS = ["good-v1", "overfit-v1", "too-few-folds"]


@pytest.fixture(autouse=True)
async def _seed_versions():
    """Seed model_versions rows for gate-testing and tear them down after each test."""
    async with session_scope() as session:
        await session.execute(text("TRUNCATE TABLE audit_log RESTART IDENTITY"))

        # Clean up any leftover rows from prior runs
        await session.execute(
            text("DELETE FROM model_versions WHERE id = ANY(:ids)"),
            {"ids": _TEST_VERSION_IDS},
        )
        await session.execute(
            text("DELETE FROM training_runs WHERE id = ANY(:ids)"),
            {"ids": _TEST_RUN_IDS},
        )

        # Insert dummy training_run rows required by FK
        await session.execute(
            text(
                """
                INSERT INTO training_runs
                    (id, model_id, status, compute_profile, as_of, train_start, train_end,
                     instruments, hyperparameters)
                VALUES
                    (:id1, 'qlib-lgbm', 'completed', 'local-cpu',
                     '2024-01-01', '2022-01-01', '2023-12-31', '{}', '{}'),
                    (:id2, 'qlib-lgbm', 'completed', 'local-cpu',
                     '2024-01-01', '2022-01-01', '2023-12-31', '{}', '{}'),
                    (:id3, 'qlib-lgbm', 'completed', 'local-cpu',
                     '2024-01-01', '2022-01-01', '2023-12-31', '{}', '{}')
                """
            ),
            {"id1": _TEST_RUN_IDS[0], "id2": _TEST_RUN_IDS[1], "id3": _TEST_RUN_IDS[2]},
        )

        # Insert model_version rows with gate metric columns
        await session.execute(
            text(
                """
                INSERT INTO model_versions
                    (id, model_id, version, stage, training_run_id,
                     pbo, dsr_probability, walk_forward_fold_count)
                VALUES
                    (:vid1, 'qlib-lgbm', 'good-v1', 'draft', :rid1,
                     0.3, 0.95, 12),
                    (:vid2, 'qlib-lgbm', 'overfit-v1', 'draft', :rid2,
                     0.85, 0.4, 12),
                    (:vid3, 'qlib-lgbm', 'too-few-folds', 'draft', :rid3,
                     0.2, 0.99, 3)
                """
            ),
            {
                "vid1": _TEST_VERSION_IDS[0],
                "vid2": _TEST_VERSION_IDS[1],
                "vid3": _TEST_VERSION_IDS[2],
                "rid1": _TEST_RUN_IDS[0],
                "rid2": _TEST_RUN_IDS[1],
                "rid3": _TEST_RUN_IDS[2],
            },
        )
        await session.commit()

    yield

    # Teardown: remove test rows
    async with session_scope() as session:
        await session.execute(
            text("DELETE FROM model_versions WHERE id = ANY(:ids)"),
            {"ids": _TEST_VERSION_IDS},
        )
        await session.execute(
            text("DELETE FROM training_runs WHERE id = ANY(:ids)"),
            {"ids": _TEST_RUN_IDS},
        )
        await session.commit()


@pytest.mark.integration
async def test_promote_succeeds_when_gates_pass(test_client):
    response = await test_client.patch(
        "/api/models/qlib-lgbm/versions/good-v1/promote",
        json={"actor": "morgan@example.com", "reason": "passes walk-forward and PBO/DSR"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["new_stage"] == "production"
    assert body["gate_results"]["pbo_pass"] is True
    assert body["gate_results"]["dsr_pass"] is True
    assert body["gate_results"]["walk_forward_pass"] is True

    async with session_scope() as session:
        stage = (
            await session.execute(
                text("SELECT stage FROM model_versions WHERE version = 'good-v1' AND model_id = 'qlib-lgbm'")
            )
        ).scalar_one()
    assert stage == "production"


@pytest.mark.integration
async def test_promote_blocks_when_pbo_too_high(test_client):
    response = await test_client.patch(
        "/api/models/qlib-lgbm/versions/overfit-v1/promote",
        json={"actor": "morgan@example.com", "reason": "should be blocked"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["gate_results"]["pbo_pass"] is False
    assert "PBO" in body["detail"]["message"]


@pytest.mark.integration
async def test_promote_blocks_when_too_few_walk_forward_folds(test_client):
    response = await test_client.patch(
        "/api/models/qlib-lgbm/versions/too-few-folds/promote",
        json={"actor": "morgan@example.com", "reason": "should be blocked"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["gate_results"]["walk_forward_pass"] is False


@pytest.mark.integration
async def test_promote_emits_audit_event(test_client):
    await test_client.patch(
        "/api/models/qlib-lgbm/versions/good-v1/promote",
        json={"actor": "morgan@example.com", "reason": "ok"},
    )
    async with session_scope() as session:
        events = (
            await session.execute(
                text(
                    """SELECT event_type, payload FROM audit_log
                       WHERE event_type = 'ModelPromoted'"""
                )
            )
        ).all()
    assert len(events) == 1
    assert events[0].payload["model_id"] == "qlib-lgbm"
    assert events[0].payload["version"] == "good-v1"
    assert events[0].payload["reason"] == "ok"
