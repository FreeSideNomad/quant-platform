"""API tests for /strategies endpoint (uses a testcontainers-backed DB)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

API_DIR = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def live_db():
    with PostgresContainer("quay.io/tembo/pg16-pgmq:latest", driver="psycopg2") as pg:
        db_url = pg.get_connection_url()
        subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            cwd=API_DIR,
            env={"DATABASE_URL": db_url, "PATH": os.environ["PATH"]},
            check=True,
        )
        yield db_url.replace("+psycopg2", "")


@pytest.fixture
def client_with_db(live_db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", live_db)
    # Reimport settings so it picks up the env var
    from importlib import reload
    from api import settings as settings_module
    reload(settings_module)
    from api import main as main_module
    reload(main_module)
    return TestClient(main_module.app)


def test_upsert_strategy_creates_new_row(client_with_db) -> None:
    resp = client_with_db.post("/strategies", json={
        "name": "my-test",
        "entry_point": "pkg.mod:main",
        "thresholds": {"pbo_max": 0.5},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] is True
    assert body["strategy_id"]


def test_upsert_strategy_updates_existing_row(client_with_db) -> None:
    # First call creates
    r1 = client_with_db.post("/strategies", json={
        "name": "my-upsert",
        "entry_point": "pkg.mod:main",
        "thresholds": {},
    })
    # Second call updates
    r2 = client_with_db.post("/strategies", json={
        "name": "my-upsert",
        "entry_point": "pkg.mod2:main",
        "thresholds": {"pbo_max": 0.7},
    })
    assert r2.json()["strategy_id"] == r1.json()["strategy_id"]
    assert r2.json()["created"] is False
