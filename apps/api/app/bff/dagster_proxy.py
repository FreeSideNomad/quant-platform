"""BFF reverse proxy for the Dagster webserver.

Mounted under /dagster/* on the BFF role. The Dagster webserver has
no built-in user auth (OSS) and is exposed only on the internal
docker / VPC network; this proxy is the sole browser-facing entry
point.

Auth flow per request:
  1. The BFF session cookie is validated (existing `load_session`).
  2. For POST /dagster/graphql the GraphQL operation type is parsed
     from the `query` string; mutations and subscriptions are gated
     to `quant` or `admin` (viewer denied 403).
  3. The request is forwarded to http://dagster-webserver:3000 with
     `X-Dagster-User-Id` / `X-Dagster-User-Email` headers injected so
     the Dagster audit trail records the real human actor.
  4. WebSocket upgrades on /dagster/graphql (used by Dagster's live
     run-log subscription) are brokered with an upstream WS client.

Streaming responses are returned via FastAPI's `StreamingResponse` so
SPA assets and large GraphQL payloads are not buffered in memory.

NOTE: The httpx.AsyncClient is created per-request — acceptable for
MVP-A. A future optimization is to use a module-level client with
connection pooling.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
import websockets
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from websockets.asyncio.client import connect as ws_connect

from app.bff.cookies import session_cookie_name
from app.bff.sessions import SessionRecord, load_session, touch_session
from app.dagster_auth.operations import classify_graphql_operation
from app.infra.db import session_scope

router = APIRouter(prefix="/dagster", tags=["dagster"])

_DAGSTER_BASE = os.environ.get("DAGSTER_WEBSERVER_URL", "http://dagster-webserver:3000")
_DAGSTER_WS_BASE = _DAGSTER_BASE.replace("http://", "ws://").replace("https://", "wss://")
_HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}
_PRIVILEGED_ROLES = {"quant", "admin"}


async def _db() -> AsyncIterator[AsyncSession]:
    async with session_scope() as s:
        yield s


async def _require_session(request: Request, db: AsyncSession = Depends(_db)) -> SessionRecord:
    sid = request.cookies.get(session_cookie_name())
    if not sid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_session")
    rec = await load_session(db, sid)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_session")
    await touch_session(db, sid)
    return rec


def _forwarded_headers(request: Request, session: SessionRecord) -> dict[str, str]:
    headers = {
        k: v for k, v in request.headers.items() if k.lower() not in _HOP_BY_HOP
    }
    headers["X-Dagster-User-Id"] = session.user_sub
    headers["X-Dagster-User-Email"] = session.user_email
    if session.user_name:
        headers["X-Dagster-User-Name"] = session.user_name
    return headers


def _response_headers(upstream: httpx.Response) -> dict[str, str]:
    return {
        k: v for k, v in upstream.headers.items()
        if k.lower() not in _HOP_BY_HOP and k.lower() != "content-encoding"
    }


async def _stream_upstream(upstream: httpx.Response) -> AsyncIterator[bytes]:
    async for chunk in upstream.aiter_raw():
        yield chunk
    await upstream.aclose()


# NOTE: The @router.post("/graphql") route MUST be registered before the
# catch-all @router.api_route("/{path:path}") route — FastAPI matches in
# registration order and the catch-all would otherwise swallow /graphql POSTs.

@router.post("/graphql")
async def graphql(request: Request, session: SessionRecord = Depends(_require_session)):
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
        set(session.roles) & _PRIVILEGED_ROLES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Dagster {operation} requires the `quant` or `admin` role; "
                f"caller has roles {session.roles!r} (viewer cannot mutate state)."
            ),
        )

    headers = _forwarded_headers(request, session)
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
    return StreamingResponse(
        _stream_upstream(upstream),
        status_code=upstream.status_code,
        headers=_response_headers(upstream),
        media_type=upstream.headers.get("content-type"),
        background=None,
    )


# NOTE: The @router.websocket("/graphql") route is registered after the
# @router.post("/graphql") route. FastAPI cleanly distinguishes HTTP POST
# routes from WebSocket routes on the same path, so there is no conflict.

@router.websocket("/graphql")
async def graphql_ws(websocket: WebSocket) -> None:
    """Broker the Dagster live-log GraphQL subscription over WebSocket."""
    sid = websocket.cookies.get(session_cookie_name())
    if not sid:
        await websocket.close(code=4401)
        return
    async with session_scope() as db:
        record = await load_session(db, sid)
    if record is None:
        await websocket.close(code=4401)
        return

    await websocket.accept(subprotocol="graphql-ws")

    upstream_headers = [
        ("X-Dagster-User-Id", record.user_sub),
        ("X-Dagster-User-Email", record.user_email),
    ]
    if record.user_name:
        upstream_headers.append(("X-Dagster-User-Name", record.user_name))

    try:
        async with ws_connect(
            f"{_DAGSTER_WS_BASE}/graphql",
            subprotocols=["graphql-ws"],
            additional_headers=upstream_headers,
            max_size=None,
        ) as upstream:
            await _bridge_websockets(websocket, upstream)
    except WebSocketDisconnect:
        return
    except websockets.exceptions.WebSocketException:
        await websocket.close(code=1011)


async def _bridge_websockets(client: WebSocket, upstream: Any) -> None:
    import asyncio

    async def client_to_upstream() -> None:
        while True:
            msg = await client.receive_text()
            await upstream.send(msg)

    async def upstream_to_client() -> None:
        async for msg in upstream:
            if isinstance(msg, bytes):
                await client.send_bytes(msg)
            else:
                await client.send_text(msg)

    done, pending = await asyncio.wait(
        {asyncio.create_task(client_to_upstream()), asyncio.create_task(upstream_to_client())},
        return_when=asyncio.FIRST_EXCEPTION,
    )
    for task in pending:
        task.cancel()


# NOTE: The catch-all route MUST be registered LAST — after the explicit
# /graphql POST and /graphql WebSocket routes — so FastAPI's route-matching
# order does not swallow those more-specific paths.

@router.api_route("/{path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def passthrough(path: str, request: Request, session: SessionRecord = Depends(_require_session)):
    """Generic proxy for static SPA assets + non-GraphQL Dagster routes."""
    body = await request.body() if request.method not in {"GET", "HEAD"} else None
    headers = _forwarded_headers(request, session)
    client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=300.0))
    upstream = await client.send(
        client.build_request(
            request.method,
            f"{_DAGSTER_BASE}/{path}",
            content=body,
            headers=headers,
            params=request.query_params,
        ),
        stream=True,
    )
    return StreamingResponse(
        _stream_upstream(upstream),
        status_code=upstream.status_code,
        headers=_response_headers(upstream),
        media_type=upstream.headers.get("content-type"),
    )
