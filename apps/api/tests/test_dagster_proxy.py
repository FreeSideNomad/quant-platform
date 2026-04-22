"""The BFF proxies the Dagster UI under /dagster/*.

Auth model:
  * Session cookie required (anonymous → 401).
  * GET requests are role-agnostic (any authenticated user can browse).
  * POST /dagster/graphql is role-gated by GraphQL operation type:
      - `query` operations: any authenticated user.
      - `mutation` / `subscription` operations: `quant` or `admin` only;
        `viewer` is denied with 403.
  * WebSocket /dagster/graphql upgrades require an authenticated session;
    the upstream WS connection is brokered by the proxy.

The Dagster webserver itself trusts proxy-injected `X-Dagster-User-*`
headers — it has no built-in auth (this is the documented OSS pattern).

The WebSocket case uses the `websockets` library directly (already a
transitive dependency from FastAPI/uvicorn) so we do not have to add
`httpx-ws` just for the test client.
"""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

# websockets >= 12 removed the legacy subpackage; use the asyncio client directly.
from websockets.asyncio.client import connect as websocket_connect


@pytest.mark.integration
async def test_dagster_root_requires_authentication(unauth_client: AsyncClient):
    response = await unauth_client.get("/dagster/")
    assert response.status_code == 401


@pytest.mark.integration
async def test_dagster_root_serves_html_for_authenticated_user(viewer_client: AsyncClient):
    response = await viewer_client.get("/dagster/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.integration
async def test_dagster_graphql_query_allowed_for_viewer(viewer_client: AsyncClient):
    response = await viewer_client.post(
        "/dagster/graphql",
        json={"query": "{ instance { info } }"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "data" in body and "instance" in body["data"]


@pytest.mark.integration
async def test_dagster_graphql_mutation_denied_for_viewer(viewer_client: AsyncClient):
    response = await viewer_client.post(
        "/dagster/graphql",
        json={
            "query": (
                "mutation Terminate($id: String!) { "
                "terminateRun(runId: $id) { __typename } }"
            ),
            "variables": {"id": "00000000-0000-0000-0000-000000000000"},
        },
    )
    assert response.status_code == 403
    assert "viewer" in response.json()["detail"].lower()


@pytest.mark.integration
async def test_dagster_graphql_mutation_allowed_for_quant(quant_client: AsyncClient):
    response = await quant_client.post(
        "/dagster/graphql",
        json={
            "query": (
                "mutation Terminate($id: String!) { "
                "terminateRun(runId: $id) { __typename } }"
            ),
            "variables": {"id": "00000000-0000-0000-0000-000000000000"},
        },
    )
    # Forwarded — Dagster will reject the unknown run id, not the BFF.
    assert response.status_code == 200
    assert "data" in response.json() or "errors" in response.json()


@pytest.mark.integration
async def test_dagster_graphql_websocket_upgrades_for_authenticated_user(
    bff_base_url: str, quant_session_cookie: str
):
    """Upgrade /dagster/graphql to a WebSocket and complete the graphql-ws
    handshake. Uses the `websockets` package directly (transitive dep of
    FastAPI/uvicorn) so no extra dependency is required."""
    ws_url = bff_base_url.replace("http://", "ws://").replace("https://", "wss://") + "/dagster/graphql"
    # websockets.asyncio.client.connect accepts additional_headers as a list of (name, value) tuples.
    additional_headers = [("Cookie", quant_session_cookie)]

    async with websocket_connect(
        ws_url,
        subprotocols=["graphql-ws"],
        additional_headers=additional_headers,
        max_size=None,
    ) as ws:
        # Send a connection_init frame and verify the upstream Dagster
        # webserver acks (or sends a keep-alive). Either reply proves the
        # BFF brokered the upgrade end-to-end.
        await ws.send(json.dumps({"type": "connection_init", "payload": {}}))
        raw = await ws.recv()
        ack = json.loads(raw)
        assert ack["type"] in {"connection_ack", "ka"}
