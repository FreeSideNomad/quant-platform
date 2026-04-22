"""Integration tests for the reproducible demo seed script (Task 7.1).

Test 1: Verifies that run_demo_seed() creates the expected rows across
        strategies, model_versions, walk_forward_folds tables.

Test 2: Verifies that the audit chain is intact after seeding — the seed
        inserts 2 audit events (StrategyRegistered + ModelPromoted) and
        verify_audit_chain() must confirm them as ok.

Timeout: 300 s — the full lineage (bronze -> silver -> gold -> walk-forward)
takes 1-2 minutes when run via dagster job execute.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.infra.db import session_scope


@pytest.mark.integration
async def test_demo_seed_creates_strategies_models_and_trained_versions(test_client):
    """Run the seed script; assert that the demo state is reproducible."""
    from app.scripts.demo_seed import run_demo_seed

    result = await run_demo_seed()

    async with session_scope() as session:
        strategy_count = (
            await session.execute(text("SELECT count(*) FROM strategies"))
        ).scalar_one()
        model_version_count = (
            await session.execute(text("SELECT count(*) FROM model_versions"))
        ).scalar_one()
        production_count = (
            await session.execute(
                text("SELECT count(*) FROM model_versions WHERE stage = 'production'")
            )
        ).scalar_one()
        wf_fold_count = (
            await session.execute(text("SELECT count(*) FROM walk_forward_folds"))
        ).scalar_one()

    assert strategy_count >= 1, f"Expected >= 1 strategy, got {strategy_count}"
    assert model_version_count >= 1, f"Expected >= 1 model_version, got {model_version_count}"
    assert production_count == 1, f"Expected exactly 1 production version, got {production_count}"
    assert wf_fold_count >= 4, f"Expected >= 4 walk-forward folds, got {wf_fold_count}"
    assert result["fold_count"] >= 4, f"Returned fold_count {result['fold_count']} < 4"


@pytest.mark.integration
async def test_demo_seed_audit_chain_passes(test_client):
    """Audit chain must be intact after the demo seed inserts 2 events."""
    from app.audit.log import verify_audit_chain
    from app.scripts.demo_seed import run_demo_seed

    await run_demo_seed()

    async with session_scope() as session:
        check = await verify_audit_chain(session)

    assert check.ok is True, f"Audit chain broken: {check.detail}"
    assert check.checked >= 2, (
        f"Expected >= 2 audit events (StrategyRegistered + ModelPromoted), "
        f"got {check.checked}"
    )
