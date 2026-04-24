"""Fixtures for SDK DB-backed tests.

Spins up a tembo pg16-pgmq testcontainer once per module, runs alembic
upgrade head (using the api package's alembic config), yields a
DATABASE_URL for the test body.
"""
from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from testcontainers.postgres import PostgresContainer

API_DIR = Path(__file__).parents[4] / "apps" / "api"


@pytest.fixture(scope="module")
def postgres_container() -> Iterator[PostgresContainer]:
    with PostgresContainer("quay.io/tembo/pg16-pgmq:latest", driver="psycopg2") as pg:
        yield pg


@pytest.fixture(scope="module")
def migrated_db_url(postgres_container: PostgresContainer) -> str:
    db_url = postgres_container.get_connection_url()
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=API_DIR,
        env={"DATABASE_URL": db_url, "PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=True,
    )
    # Strip SQLAlchemy driver suffix so psycopg2 can use it directly.
    return db_url.replace("+psycopg2", "")


@pytest.fixture
def db_url_env(migrated_db_url: str, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("DATABASE_URL", migrated_db_url)
    return migrated_db_url
