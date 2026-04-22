"""SDK-facing GraphQL passthrough to the internal Dagster webserver.

Mounted at /api/dagster-graphql on the `api` role. The shape matches
Dagster's own /graphql endpoint exactly so the upstream
`dagster_graphql.DagsterGraphQLClient` library works against this URL
unmodified — the SDK passes its Bearer JWT in the Authorization
header and the request is forwarded to Dagster with proxy-injected
`X-Dagster-User-*` identity headers.

Mutation / subscription operations require the `quant` or `admin`
role; queries are open to any authenticated user.

Example SDK use (Marimo notebook):

    from dagster_graphql import DagsterGraphQLClient
    client = DagsterGraphQLClient(
        url=f"{platform_url}/api/dagster-graphql",
        headers={"Authorization": f"Bearer {token}"},
    )
    client.submit_pipeline_execution(...)
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.api.auth_deps import AuthenticatedUser, get_current_user
from app.dagster_auth.operations import classify_graphql_operation

router = APIRouter(prefix="/api", tags=["dagster"])

_DAGSTER_BASE = os.environ.get("DAGSTER_WEBSERVER_URL", "http://dagster-webserver:3000")
_PRIVILEGED_ROLES = {"quant", "admin"}
_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
    "authorization",
}


def _forwarded_headers(request: Request, user: AuthenticatedUser) -> dict[str, str]:
    headers = {k: v for k, v in request.headers.items() if k.lower() not in _HOP_BY_HOP}
    headers["X-Dagster-User-Id"] = user.sub
    headers["X-Dagster-User-Email"] = user.email
    if user.name:
        headers["X-Dagster-User-Name"] = user.name
    return headers


async def _stream_upstream(upstream: httpx.Response) -> AsyncIterator[bytes]:
    async for chunk in upstream.aiter_raw():
        yield chunk
    await upstream.aclose()


@router.post("/dagster-graphql")
async def dagster_graphql(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> StreamingResponse:
    body = await request.body()
    query_text = ""
    try:
        payload: Any = await request.json()
        if isinstance(payload, dict) and isinstance(payload.get("query"), str):
            query_text = payload["query"]
    except ValueError:
        pass

    operation = classify_graphql_operation(query_text)
    if operation in {"mutation", "subscription"} and not (
        set(user.roles) & _PRIVILEGED_ROLES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Dagster {operation} requires the `quant` or `admin` role; "
                f"caller has roles {user.roles!r}."
            ),
        )

    headers = _forwarded_headers(request, user)
    client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=300.0))
    upstream = await client.send(
        client.build_request(
            "POST",
            f"{_DAGSTER_BASE}/graphql",
            content=body,
            headers=headers,
            params=request.query_params,
        ),
        stream=True,
    )
    response_headers = {
        k: v
        for k, v in upstream.headers.items()
        if k.lower() not in _HOP_BY_HOP and k.lower() != "content-encoding"
    }
    return StreamingResponse(
        _stream_upstream(upstream),
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=upstream.headers.get("content-type"),
    )
