"""Verify alembic downgrade base && upgrade head works on a clean DB.

Port of the `testcontainers migration roundtrip` pattern from MVP-A
(LESSONS.md §worth-keeping).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from testcontainers.postgres import PostgresContainer

API_DIR = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def postgres_container():
    # Use the tembo pg16-pgmq image so the pgmq extension is available.
    with PostgresContainer("quay.io/tembo/pg16-pgmq:latest", driver="psycopg2") as pg:
        yield pg


def _run_alembic(args: list[str], db_url: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=API_DIR,
        env={"DATABASE_URL": db_url, "PATH": __import__("os").environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
    )


def test_alembic_upgrade_head(postgres_container) -> None:
    db_url = postgres_container.get_connection_url()  # psycopg2 URL
    result = _run_alembic(["upgrade", "head"], db_url)
    assert result.returncode == 0, result.stderr


def test_alembic_downgrade_base_then_upgrade_head(postgres_container) -> None:
    db_url = postgres_container.get_connection_url()
    result = _run_alembic(["downgrade", "base"], db_url)
    assert result.returncode == 0, result.stderr
    result = _run_alembic(["upgrade", "head"], db_url)
    assert result.returncode == 0, result.stderr


def test_m3_tables_created_by_head(postgres_container) -> None:
    """After `alembic upgrade head`, the six M3 tables must exist."""
    db_url = postgres_container.get_connection_url()
    result = _run_alembic(["upgrade", "head"], db_url)
    assert result.returncode == 0, result.stderr

    import psycopg2
    # get_connection_url() returns a SQLAlchemy URL like
    # "postgresql+psycopg2://..."; strip the driver prefix so psycopg2
    # can parse it as a plain libpq DSN.
    plain_url = db_url.replace("postgresql+psycopg2://", "postgresql://", 1)
    conn = psycopg2.connect(plain_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public'"
            )
            tables = {r[0] for r in cur.fetchall()}
    finally:
        conn.close()

    expected = {"strategies", "runs", "events", "datasets", "dataset_versions", "lineage_reads"}
    missing = expected - tables
    assert not missing, f"missing tables: {missing}"
