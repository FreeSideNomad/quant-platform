"""Unit tests for /internal/health — exercises FastAPI without touching the database."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.mark.unit
def test_health_returns_ok() -> None:
    client = TestClient(create_app())
    resp = client.get("/internal/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["role"] == "api"
    assert "version" in body
