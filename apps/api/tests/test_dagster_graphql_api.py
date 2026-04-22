"""SDK-facing /api/dagster-graphql endpoint with Bearer JWT auth.

Auth model:
  * Bearer JWT required (no token → 401).
  * GET requests are not supported; only POST.
  * POST /api/dagster-graphql is role-gated by GraphQL operation type:
      - `query` operations: any authenticated user.
      - `mutation` / `subscription` operations: `quant` or `admin` only;
        `viewer` is denied with 403.

The endpoint mirrors Dagster's own /graphql shape so the upstream
`dagster_graphql.DagsterGraphQLClient` SDK works against it unchanged.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_dagster_graphql_api_requires_bearer(unauth_api_client: AsyncClient):
    """No Bearer token → 401 from the API role directly."""
    response = await unauth_api_client.post(
        "/api/dagster-graphql",
        json={"query": "{ instance { info } }"},
    )
    assert response.status_code == 401


@pytest.mark.integration
async def test_dagster_graphql_api_query_allowed_for_viewer(viewer_bearer_client: AsyncClient):
    """Viewer with Bearer JWT can execute GraphQL queries."""
    response = await viewer_bearer_client.post(
        "/api/dagster-graphql",
        json={"query": "{ instance { info } }"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "data" in body and "instance" in body["data"]


@pytest.mark.integration
async def test_dagster_graphql_api_mutation_denied_for_viewer(viewer_bearer_client: AsyncClient):
    """Viewer with Bearer JWT cannot execute GraphQL mutations → 403."""
    response = await viewer_bearer_client.post(
        "/api/dagster-graphql",
        json={
            "query": (
                "mutation Terminate($id: String!) { "
                "terminateRun(runId: $id) { __typename } }"
            ),
            "variables": {"id": "00000000-0000-0000-0000-000000000000"},
        },
    )
    assert response.status_code == 403


@pytest.mark.integration
async def test_dagster_graphql_api_mutation_allowed_for_quant(quant_bearer_client: AsyncClient):
    """Quant with Bearer JWT can execute GraphQL mutations; Dagster may reject the run id."""
    response = await quant_bearer_client.post(
        "/api/dagster-graphql",
        json={
            "query": (
                "mutation Terminate($id: String!) { "
                "terminateRun(runId: $id) { __typename } }"
            ),
            "variables": {"id": "00000000-0000-0000-0000-000000000000"},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "data" in payload or "errors" in payload
