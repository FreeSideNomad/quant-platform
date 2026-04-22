import pytest
from sqlalchemy import text

from app.infra.db import session_scope


@pytest.fixture(autouse=True)
async def _clean():
    async with session_scope() as session:
        await session.execute(text("TRUNCATE TABLE strategies, audit_log RESTART IDENTITY"))
        await session.commit()
    yield


SAMPLE_SPEC = {
    "feature_set": {
        "name": "csi300_alpha158_v1",
        "universe": "csi300_top_constituents",
        "sources": {"alpha158": "gold.csi300_alpha158"},
        "columns": [{"source": "alpha158", "name": "*"}],
        "target": {"source": "alpha158", "name": "label_return_5d"},
    },
    "model_class": "csi300_alpha158_v1.CSI300Alpha158LightGBM",
    "strategy_class": "csi300_alpha158_v1.CSI300LongShortDecile",
    "walk_forward": {
        "step": "quarter", "train_window": "3y", "test_window": "1q", "min_folds": 8,
    },
    "backtest": {
        "cost_model": "almgren_chriss", "capacity_aum_usd": 500_000_000, "benchmark": "CSI300",
    },
    "serving_schedule": "daily 15:00 CST",
}


@pytest.mark.integration
async def test_register_strategy_persists_to_strategies_table(test_client):
    response = await test_client.post(
        "/api/commands/RegisterStrategy",
        json={"family": "csi300_long_short_alpha158", "spec": SAMPLE_SPEC, "actor": "morgan@example.com"},
    )
    assert response.status_code == 201
    body = response.json()
    assert "strategy_id" in body
    assert body["family"] == "csi300_long_short_alpha158"

    async with session_scope() as session:
        row = (
            await session.execute(
                text("SELECT family, registered_by FROM strategies WHERE id = :id"),
                {"id": body["strategy_id"]},
            )
        ).one()
    assert row.family == "csi300_long_short_alpha158"
    assert row.registered_by == "morgan@example.com"


@pytest.mark.integration
async def test_register_strategy_emits_audit_event(test_client):
    response = await test_client.post(
        "/api/commands/RegisterStrategy",
        json={"family": "f1", "spec": SAMPLE_SPEC, "actor": "morgan@example.com"},
    )
    strategy_id = response.json()["strategy_id"]

    async with session_scope() as session:
        audit = (
            await session.execute(
                text(
                    """SELECT event_type, aggregate_type, aggregate_id, payload
                       FROM audit_log WHERE aggregate_id = :id"""
                ),
                {"id": strategy_id},
            )
        ).one()

    assert audit.event_type == "StrategyRegistered"
    assert audit.aggregate_type == "Strategy"
    assert audit.aggregate_id == strategy_id


@pytest.mark.integration
async def test_register_strategy_idempotent_on_same_spec_hash(test_client):
    r1 = await test_client.post(
        "/api/commands/RegisterStrategy",
        json={"family": "f1", "spec": SAMPLE_SPEC, "actor": "morgan@example.com"},
    )
    r2 = await test_client.post(
        "/api/commands/RegisterStrategy",
        json={"family": "f1", "spec": SAMPLE_SPEC, "actor": "morgan@example.com"},
    )
    assert r1.status_code == 201
    assert r2.status_code == 200  # no-op replay; returns existing
    assert r1.json()["strategy_id"] == r2.json()["strategy_id"]


@pytest.mark.integration
async def test_register_strategy_validates_spec_shape(test_client):
    bad_spec = {"family": "f1", "spec": {"missing": "fields"}, "actor": "x@example.com"}
    response = await test_client.post("/api/commands/RegisterStrategy", json=bad_spec)
    assert response.status_code == 422


@pytest.mark.integration
async def test_register_strategy_rejects_oversize_spec(test_client):
    """A spec larger than 64 KB is rejected with 422."""
    bloat = {f"{'x' * 50}{i}": "y" * 1000 for i in range(100)}  # ~100 KB
    spec_with_bloat = {**SAMPLE_SPEC, "bloat": bloat}
    response = await test_client.post(
        "/api/commands/RegisterStrategy",
        json={"family": "f1", "spec": spec_with_bloat, "actor": "morgan@example.com"},
    )
    assert response.status_code == 422
    assert "spec exceeds maximum size" in str(response.json())


@pytest.mark.integration
async def test_register_strategy_rejects_bad_family_chars(test_client):
    """A family with shell-injection-style chars is rejected."""
    response = await test_client.post(
        "/api/commands/RegisterStrategy",
        json={
            "family": "../../etc/passwd",
            "spec": SAMPLE_SPEC,
            "actor": "morgan@example.com",
        },
    )
    assert response.status_code == 422


@pytest.mark.integration
async def test_register_strategy_rejects_bad_actor_email(test_client):
    """Actor must be a valid email address."""
    response = await test_client.post(
        "/api/commands/RegisterStrategy",
        json={"family": "f1", "spec": SAMPLE_SPEC, "actor": "not-an-email"},
    )
    assert response.status_code == 422

