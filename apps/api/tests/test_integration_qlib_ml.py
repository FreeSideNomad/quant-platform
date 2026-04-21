"""End-to-end integration test for the Qlib-style ML pipeline.

Full flow:
  1. Login as admin
  2. Submit a training run (local-cpu profile)
  3. Wait for worker-training to complete it
  4. Verify model version is registered and promoted
  5. Invoke the inference endpoint and receive a prediction
  6. Verify the inference log contains the request

Requires docker-compose stack up and migrated.
"""

from __future__ import annotations

import asyncio
import re

import httpx
import pytest

BFF_URL = "http://localhost:8080"
MOCK_URL = "http://localhost:9800"


async def _login_admin(client: httpx.AsyncClient) -> str:
    r = await client.get(f"{BFF_URL}/auth/login", params={"return_to": "/auth/me"})
    r = await client.get(r.headers["location"])
    r = await client.get(r.headers["location"])
    rid = re.search(r'name="request_id"\s+value="([^"]+)"', r.text).group(1)
    r = await client.post(
        f"{MOCK_URL}/authorize/submit",
        data={"request_id": rid, "username": "admin", "password": "admin"},
    )
    r = await client.get(r.headers["location"])
    r = await client.get(r.headers["location"])
    return client.cookies["qp_csrf"]


async def _wait_for_run(
    client: httpx.AsyncClient, run_id: str, *, timeout_s: float = 120.0
) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_s
    last_status = None
    while asyncio.get_event_loop().time() < deadline:
        r = await client.get(f"{BFF_URL}/api/models/qlib-lgbm")
        assert r.status_code == httpx.codes.OK
        runs = r.json().get("training_runs", [])
        run = next((x for x in runs if x["id"] == run_id), None)
        if run is None:
            await asyncio.sleep(1.0)
            continue
        last_status = run["status"]
        if run["status"] in ("completed", "failed"):
            return run
        await asyncio.sleep(1.0)
    raise AssertionError(f"training run {run_id} timed out, last status={last_status}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_train_register_predict() -> None:
    async with httpx.AsyncClient(follow_redirects=False, timeout=180.0) as client:
        csrf = await _login_admin(client)

        r = await client.post(
            f"{BFF_URL}/api/training/submit",
            json={
                "model_id": "qlib-lgbm",
                "compute_profile": "local-cpu",
                "as_of": "2024-12-31",
                "train_start": "2022-01-01",
                "train_end": "2024-06-30",
                "instruments": [],
                "hyperparameters": {"num_leaves": 15},
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert r.status_code == httpx.codes.OK, r.text
        run_id = r.json()["training_run_id"]

        run = await _wait_for_run(client, run_id)
        assert run["status"] == "completed", run.get("error")
        assert run["model_version"] is not None
        assert "val_rmse" in (run.get("metrics", {}).get("metrics") or {})

        r = await client.post(
            f"{BFF_URL}/api/serving/qlib-lgbm/predict",
            json={"instrument": "QPX.A", "as_of": "2024-12-31"},
            headers={"X-CSRF-Token": csrf},
        )
        assert r.status_code == httpx.codes.OK, r.text
        body = r.json()
        assert isinstance(body["prediction"], (int, float))
        assert body["model_version"] == run["model_version"]
        assert body["latency_ms"] >= 0

        r = await client.get(f"{BFF_URL}/api/models/qlib-lgbm/inference-log?limit=5")
        assert r.status_code == httpx.codes.OK
        log = r.json()
        assert any(e["id"] == body["inference_id"] and e["instrument"] == "QPX.A" for e in log), log
