# apps/api/tests/test_audit_verify_cli.py
"""Integration tests for the audit-verify CLI command."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

from app.audit.log import append_audit_event
from app.infra.db import session_scope

REPO_ROOT = Path(__file__).resolve().parents[3]  # quant-platform/


def _run_cli() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "app.cli.audit_verify"],
        cwd=REPO_ROOT / "apps" / "api",
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.integration
async def test_audit_verify_reports_ok_on_clean_chain():
    """Seed 3 events, run CLI, assert exit_code=0 and stdout contains ok=True and checked=3."""
    async with session_scope() as session:
        for i in range(3):
            await append_audit_event(
                session,
                actor="test",
                event_type="StrategyRegistered",
                aggregate_type="Strategy",
                aggregate_id=f"s{i}",
                payload={"i": i},
            )

    result = _run_cli()
    assert result.returncode == 0, f"CLI exited {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}"
    assert "ok=True" in result.stdout, f"Expected 'ok=True' in stdout: {result.stdout!r}"
    assert "checked=3" in result.stdout, f"Expected 'checked=3' in stdout: {result.stdout!r}"


@pytest.mark.integration
async def test_audit_verify_detects_tamper():
    """Seed 1 event, tamper its payload bypassing the trigger, assert exit_code!=0 and ok=False."""
    async with session_scope() as session:
        event_id = await append_audit_event(
            session,
            actor="test",
            event_type="StrategyRegistered",
            aggregate_type="Strategy",
            aggregate_id="s0",
            payload={"i": 0},
        )

    # Tamper the payload bypassing the immutability trigger via session_replication_role.
    async with session_scope() as session:
        await session.execute(text("SET LOCAL session_replication_role = replica"))
        await session.execute(
            text("UPDATE audit_log SET payload = '{\"i\": 999}'::jsonb WHERE id = :id"),
            {"id": event_id},
        )
        await session.commit()

    result = _run_cli()
    assert result.returncode != 0, f"CLI should exit non-zero; stdout={result.stdout!r}; stderr={result.stderr!r}"
    assert "ok=False" in result.stdout, f"Expected 'ok=False' in stdout: {result.stdout!r}"
    assert f"first_break={event_id}" in result.stdout, f"Expected 'first_break={event_id}' in stdout: {result.stdout!r}"
