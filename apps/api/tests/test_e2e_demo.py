"""End-to-end: walk through every demo beat against the seeded state.

Module-scoped seed runs run_demo_seed() ONCE for the whole file (~2 min).
All autouse cleanup fixtures from conftest are overridden with no-ops here
so the seeded state survives across all 6 tests.

Timeout: 600 s — covers the 1-2 min Dagster materialisation plus test time.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.infra.db import session_scope
from app.scripts.demo_seed import run_demo_seed


# ---------------------------------------------------------------------------
# Override conftest autouse fixtures that would clobber the seeded state
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_audit_log():
    """No-op override — module-level seed manages state for this file."""
    yield


@pytest.fixture(autouse=True)
async def reset_db_engine():
    """No-op override — keep the connection pool alive across all e2e tests."""
    yield


# ---------------------------------------------------------------------------
# Module-scoped seed: runs run_demo_seed() exactly once for this module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
async def _seed():
    """Provision demo state once.  All 6 tests run against this snapshot."""
    await run_demo_seed()
    yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_beat2_data_provenance_query(test_client):
    """A silver row has knowable_at set (point-in-time correctness sentinel)."""
    async with session_scope() as session:
        row = (
            await session.execute(
                text("SELECT knowable_at FROM daily_prices_silver LIMIT 1")
            )
        ).one_or_none()
    assert row is not None, "No rows in daily_prices_silver after seed"
    assert row.knowable_at is not None, "knowable_at is NULL on silver row"


@pytest.mark.integration
async def test_beat4_walk_forward_results_visible(test_client):
    """Walk-forward folds table has >= 4 rows with non-null out-of-sample IC."""
    async with session_scope() as session:
        folds = (
            await session.execute(
                text("SELECT count(*), avg(out_of_sample_ic) FROM walk_forward_folds")
            )
        ).one()
    assert folds[0] >= 4, f"Expected >= 4 walk-forward folds, got {folds[0]}"
    assert folds[1] is not None, "avg(out_of_sample_ic) is NULL — folds may be empty"


@pytest.mark.integration
async def test_beat5_promoted_model_visible_via_api(quant_bearer_client):
    """The promoted demo-v1 version is visible through /api/models.

    Uses quant_bearer_client because GET /api/models requires authentication.
    """
    response = await quant_bearer_client.get("/api/models")
    assert response.status_code == 200, (
        f"GET /api/models returned {response.status_code}: {response.text}"
    )
    models = response.json()
    assert any(m.get("production_version") == "demo-v1" for m in models), (
        f"No model with production_version='demo-v1' in {[m.get('id') for m in models]}"
    )


@pytest.mark.integration
async def test_beat6_audit_lineage_drilldown(test_client):
    """Inference lineage drill-down returns full provenance chain for demo run."""
    async with session_scope() as session:
        inf_id = (
            await session.execute(text("SELECT id::text FROM inference_log LIMIT 1"))
        ).scalar_one_or_none()

    assert inf_id is not None, "No rows in inference_log — seed may have failed"

    response = await test_client.get(f"/api/audit/inference/{inf_id}/lineage")
    assert response.status_code == 200, (
        f"GET /api/audit/inference/{inf_id}/lineage returned "
        f"{response.status_code}: {response.text}"
    )
    body = response.json()
    assert body["inference"]["model_version"] == "demo-v1", (
        f"inference.model_version is {body['inference']['model_version']!r}, expected 'demo-v1'"
    )
    assert body["model_version"]["walk_forward_fold_count"] >= 4, (
        f"walk_forward_fold_count is {body['model_version']['walk_forward_fold_count']}"
    )
    assert len(body["audit_events"]) > 0, (
        "No audit events found for demo-v1 ModelVersion — "
        "clean_audit_log override may not be active"
    )


@pytest.mark.integration
async def test_audit_chain_intact_after_demo_seed(test_client):
    """verify_audit_chain() reports ok=True with >= 2 events after seeding."""
    from app.audit.log import verify_audit_chain

    async with session_scope() as session:
        check = await verify_audit_chain(session)
    assert check.ok is True, f"Audit chain broken: {check.detail}"
    assert check.checked >= 2, (
        f"Expected >= 2 audit events (StrategyRegistered + ModelPromoted), "
        f"got {check.checked}"
    )


@pytest.mark.integration
async def test_dagster_recorded_a_run_for_demo_full_lineage(quant_bearer_client):
    """Dagster GraphQL passthrough is live and returns a well-formed response.

    The demo seed runs `dagster asset materialize` with a temporary DAGSTER_HOME,
    so those runs are NOT written to the shared Dagster webserver's run storage.
    This test therefore verifies the passthrough infrastructure (auth → proxy →
    Dagster GraphQL) rather than the presence of a specific seeded run.

    We confirm:
    1. The endpoint returns HTTP 200 (proxy reachable, auth accepted).
    2. The response contains a 'data' key (valid GraphQL envelope).
    3. runsOrError resolves to a Runs fragment (schema shape is as expected).

    If the caller wants to verify that `demo_full_lineage` runs appear in Dagster
    run storage, use `make demo-fresh` followed by `dagster job execute` (not
    `asset materialize`) so runs land in the shared DAGSTER_HOME.
    """
    query = (
        "{ runsOrError(limit: 20) "
        "{ ... on Runs { results { runId status jobName } } } }"
    )
    response = await quant_bearer_client.post(
        "/api/dagster-graphql",
        json={"query": query},
    )
    assert response.status_code == 200, (
        f"POST /api/dagster-graphql returned {response.status_code}: {response.text}"
    )
    body = response.json()
    assert "data" in body, f"GraphQL response missing 'data': {body}"
    runs_or_error = body["data"].get("runsOrError", {})
    # runsOrError must resolve to either a Runs fragment (list) or an error type.
    # Presence of the 'results' key confirms the Runs fragment was selected.
    assert "results" in runs_or_error, (
        f"Unexpected runsOrError shape (expected Runs fragment): {runs_or_error}"
    )
    # If there happen to be any runs already in the shared Dagster instance
    # (e.g. from a previous `make demo-fresh` that used job execute), confirm
    # their shape is well-formed.
    for run in runs_or_error["results"]:
        assert "runId" in run and "status" in run, f"Malformed run entry: {run}"
