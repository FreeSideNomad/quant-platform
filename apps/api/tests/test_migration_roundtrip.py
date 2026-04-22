"""Migration roundtrip: alembic downgrade base + upgrade head against a
throwaway Postgres. Catches broken downgrade() methods before production
needs them.

Uses testcontainers to spin up an isolated Postgres so this test does
not affect the local docker-compose Postgres (which holds all the other
integration tests' state).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

try:
    from testcontainers.postgres import PostgresContainer

    HAS_TESTCONTAINERS = True
except ImportError:
    HAS_TESTCONTAINERS = False


_API_DIR = Path(__file__).resolve().parents[1]


@pytest.mark.integration
@pytest.mark.destructive
@pytest.mark.skipif(not HAS_TESTCONTAINERS, reason="testcontainers not installed")
def test_alembic_downgrade_base_then_upgrade_head_against_isolated_postgres():
    """Spin up a throwaway Postgres, apply all migrations, downgrade to base,
    re-apply head, and assert no errors. Validates downgrade() correctness."""

    with PostgresContainer(
        "ghcr.io/pgmq/pg17-pgmq:latest",
        username="quant",
        password="quant",
        dbname="quant",
    ) as pg:
        # get_connection_url() returns postgresql+psycopg2://...
        # Alembic env.py uses async_engine_from_config which needs asyncpg.
        url = pg.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://"
        )

        env = {
            **os.environ,
            "DATABASE_URL": url,
        }

        # --- Step 1: apply all migrations ---
        result = subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            cwd=_API_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"upgrade head failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

        # --- Step 2: record current head ---
        result = subprocess.run(
            ["uv", "run", "alembic", "current"],
            cwd=_API_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"alembic current (before) failed:\nSTDERR:\n{result.stderr}"
        )
        head_before = result.stdout.strip()
        assert head_before, "alembic current returned empty output after upgrade head"

        # --- Step 3: downgrade all the way to base ---
        result = subprocess.run(
            ["uv", "run", "alembic", "downgrade", "base"],
            cwd=_API_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"downgrade base failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

        # --- Step 4: re-upgrade to head ---
        result = subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            cwd=_API_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"upgrade head (second time) failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

        # --- Step 5: confirm head matches what we started with ---
        result = subprocess.run(
            ["uv", "run", "alembic", "current"],
            cwd=_API_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"alembic current (after) failed:\nSTDERR:\n{result.stderr}"
        )
        head_after = result.stdout.strip()

        assert head_after == head_before, (
            f"head changed across roundtrip:\n  before: {head_before!r}\n  after:  {head_after!r}"
        )
