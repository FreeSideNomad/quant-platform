"""BFF routes — auth redirect flow, proxy to upstream API, logout."""

from __future__ import annotations

import base64
import secrets
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from hashlib import sha256
from urllib.parse import urlencode

import httpx
import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.bff.cookies import (
    CSRF_COOKIE_NAME,
    clear_session_cookies,
    session_cookie_name,
    set_csrf_cookie,
    set_session_cookie,
)
from app.bff.sessions import (
    create_session,
    load_session,
    revoke_session,
    rotate_session_id,
    touch_session,
)
from app.config import get_settings
from app.infra.db import session_scope

router = APIRouter()


def _pkce_challenge(verifier: str) -> str:
    digest = sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


async def db() -> AsyncIterator[AsyncSession]:
    async with session_scope() as session:
        yield session


# ---------------------------------------------------------------------------
# /auth/login  — start the redirect flow
# ---------------------------------------------------------------------------
@router.get("/auth/login")
async def login(request: Request, db: AsyncSession = Depends(db)) -> RedirectResponse:
    settings = get_settings()
    return_to = request.query_params.get("return_to", "/")
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    code_verifier = secrets.token_urlsafe(48)
    challenge = _pkce_challenge(code_verifier)
    await db.execute(
        text(
            "INSERT INTO auth_states(state, nonce, code_verifier, return_to, expires_at) "
            "VALUES (:s, :n, :v, :rt, now() + interval '10 minutes')"
        ),
        {"s": state, "n": nonce, "v": code_verifier, "rt": return_to},
    )
    authorize_params = {
        "response_type": "code",
        "client_id": settings.idp_client_id,
        "redirect_uri": f"{settings.bff_public_url}/auth/callback",
        "scope": "openid email profile",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return RedirectResponse(f"{settings.idp_issuer}/authorize?{urlencode(authorize_params)}")


# ---------------------------------------------------------------------------
# /auth/callback — exchange code, create server-side session
# ---------------------------------------------------------------------------
@router.get("/auth/callback")
async def callback(
    request: Request, code: str, state: str, db: AsyncSession = Depends(db)
) -> Response:
    settings = get_settings()
    row = await db.execute(
        text(
            "DELETE FROM auth_states WHERE state = :s AND expires_at > now() "
            "RETURNING code_verifier, return_to"
        ),
        {"s": state},
    )
    hit = row.first()
    if hit is None:
        raise HTTPException(status_code=400, detail="invalid_state")
    code_verifier, return_to = hit

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{settings.idp_internal_url}/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"{settings.bff_public_url}/auth/callback",
                "client_id": settings.idp_client_id,
                "client_secret": settings.idp_client_secret,
                "code_verifier": code_verifier,
            },
        )
        if resp.is_error:
            raise HTTPException(status_code=400, detail=f"token_exchange_failed: {resp.text}")
        tokens = resp.json()

    # Decode our id_token to extract user claims. Verify=False is safe because we
    # fetched it over a trusted server-to-server channel directly from our own IdP;
    # the browser never sees the token.
    claims = pyjwt.decode(tokens["id_token"], options={"verify_signature": False})

    access_exp = datetime.fromtimestamp(
        datetime.now(UTC).timestamp() + tokens.get("expires_in", 900), tz=UTC
    )
    # Approximate refresh expiry — the issuer knows the real one; we store from config.
    refresh_exp = datetime.fromtimestamp(
        datetime.now(UTC).timestamp() + settings.idp_refresh_token_ttl_seconds, tz=UTC
    )

    record = await create_session(
        db,
        user_sub=str(claims["sub"]),
        user_email=str(claims.get("email", "")),
        user_name=claims.get("name"),
        roles=list(claims.get("roles", [])),
        tenant_id=claims.get("tenant_id"),
        upstream_idp=str(claims.get("upstream_idp", "unknown")),
        upstream_sub=claims.get("upstream_sub"),
        id_token=tokens["id_token"],
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        access_expires_at=access_exp,
        refresh_expires_at=refresh_exp,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    response = RedirectResponse(return_to or "/", status_code=302)
    max_age = settings.bff_session_absolute_seconds
    set_session_cookie(response, record.id, max_age_seconds=max_age)
    set_csrf_cookie(response, record.csrf_token, max_age_seconds=max_age)
    return response


# ---------------------------------------------------------------------------
# /auth/logout
# ---------------------------------------------------------------------------
@router.post("/auth/logout")
@router.get("/auth/logout")
async def logout(request: Request, db: AsyncSession = Depends(db)) -> Response:
    sid = request.cookies.get(session_cookie_name())
    if sid:
        await revoke_session(db, sid)
    response = RedirectResponse("/", status_code=302)
    clear_session_cookies(response)
    return response


# ---------------------------------------------------------------------------
# /auth/me — the current user; used by the SPA to decide to render
# ---------------------------------------------------------------------------
@router.get("/auth/me")
async def me(request: Request, db: AsyncSession = Depends(db)) -> dict[str, object]:
    sid = request.cookies.get(session_cookie_name())
    if not sid:
        raise HTTPException(status_code=401, detail="no_session")
    rec = await load_session(db, sid)
    if rec is None:
        raise HTTPException(status_code=401, detail="invalid_session")
    await touch_session(db, sid)
    return {
        "sub": rec.user_sub,
        "email": rec.user_email,
        "name": rec.user_name,
        "roles": rec.roles,
        "tenant_id": rec.tenant_id,
    }


# ---------------------------------------------------------------------------
# /api/*  — authenticated reverse proxy to the upstream API.
# For unauthenticated traffic on /api/*, redirect to login with return_to.
# ---------------------------------------------------------------------------
@router.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def proxy_api(path: str, request: Request, db: AsyncSession = Depends(db)) -> Response:
    settings = get_settings()
    sid = request.cookies.get(session_cookie_name())
    if not sid:
        # For API calls we return 401 rather than redirecting (SPA handles the redirect).
        raise HTTPException(status_code=401, detail="no_session")

    rec = await load_session(db, sid)
    if rec is None:
        raise HTTPException(status_code=401, detail="invalid_session")

    # CSRF check on mutating methods.
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        header_token = request.headers.get("x-csrf-token")
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        if not header_token or header_token != cookie_token or header_token != rec.csrf_token:
            raise HTTPException(status_code=403, detail="csrf_mismatch")

    await touch_session(db, sid)

    # Optionally rotate session id on token refresh (not exercised here but the hook exists).
    if rec.access_expires_at.timestamp() < datetime.now(UTC).timestamp() + 30 and rec.refresh_token:
        await rotate_session_id(db, sid)

    upstream = f"{settings.bff_upstream_api_url}/{path}"
    headers_out = dict(request.headers)
    for h in ("host", "cookie", "content-length"):
        headers_out.pop(h, None)
    headers_out["authorization"] = f"Bearer {rec.access_token}"
    headers_out["x-user-sub"] = rec.user_sub
    headers_out["x-user-email"] = rec.user_email
    headers_out["x-user-roles"] = ",".join(rec.roles)
    if rec.tenant_id:
        headers_out["x-tenant-id"] = rec.tenant_id

    body = await request.body()
    async with httpx.AsyncClient(timeout=30.0) as client:
        upstream_resp = await client.request(
            method=request.method,
            url=upstream,
            params=dict(request.query_params),
            content=body,
            headers=headers_out,
        )

    _hop_by_hop = {"content-encoding", "transfer-encoding", "connection"}
    resp_headers = {k: v for k, v in upstream_resp.headers.items() if k.lower() not in _hop_by_hop}
    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        headers=resp_headers,
        media_type=upstream_resp.headers.get("content-type"),
    )


# Unauthenticated guard for page routes: anything that is not /auth/* or /api/* is a
# page request. If no session cookie, redirect to /auth/login with return_to.
@router.api_route("/{path:path}", methods=["GET"], include_in_schema=False)
async def catch_all(path: str, request: Request) -> Response:
    if path.startswith(("auth/", "api/")):
        raise HTTPException(status_code=404)
    sid = request.cookies.get(session_cookie_name())
    if sid is None:
        return_to = f"/{path}" if path else "/"
        return RedirectResponse(f"/auth/login?return_to={return_to}", status_code=302)
    # Authenticated page request — proxy to the SPA served by the API (or Vite dev in dev).
    # For the MVP, forward to the upstream API at `/` which hosts the SPA.
    settings = get_settings()
    upstream = f"{settings.bff_upstream_api_url}/{path}"
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
        upstream_resp = await client.get(
            upstream,
            headers={"accept": request.headers.get("accept", "*/*")},
        )
    # Stream through
    return StreamingResponse(
        iter([upstream_resp.content]),
        status_code=upstream_resp.status_code,
        media_type=upstream_resp.headers.get("content-type"),
    )
