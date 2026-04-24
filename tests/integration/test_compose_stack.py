"""End-to-end: bring up the full compose stack and verify all services healthy."""
from __future__ import annotations

import httpx
import pytest
from tenacity import retry, stop_after_delay, wait_fixed


@retry(stop=stop_after_delay(30), wait=wait_fixed(1), reraise=True)
def _get(url: str) -> httpx.Response:
    return httpx.get(url, timeout=5.0)


@pytest.mark.usefixtures("compose_up")
class TestComposeStack:
    def test_api_health(self) -> None:
        response = _get("http://localhost:18000/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_mlflow_health(self) -> None:
        response = _get("http://localhost:15000/health")
        assert response.status_code == 200

    def test_minio_health(self) -> None:
        response = _get("http://localhost:19000/minio/health/ready")
        assert response.status_code == 200

    def test_mock_oidc_health(self) -> None:
        response = _get("http://localhost:14444/.well-known/openid-configuration")
        assert response.status_code == 200
        assert response.json()["issuer"].startswith("http://localhost")

    def test_ui_root(self) -> None:
        response = _get("http://localhost:15173")
        assert response.status_code == 200
