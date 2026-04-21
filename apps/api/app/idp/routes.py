"""OIDC endpoints served by the IdP role.

Exposes:
- /.well-known/openid-configuration
- /jwks
- /authorize  (redirects to the upstream IdP with PKCE)
- /auth/callback  (consumes the upstream auth code; issues our tokens)
- /userinfo
- /token  (refresh-token grant against our tokens)
"""

from __future__ import annotations

import base64
import json
import secrets
import time
from collections.abc import AsyncIterator
from hashlib import sha256
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.idp.keys import jwks_document
from app.idp.tokens import UpstreamIdentity, mint_tokens, verify_token
from app.idp.upstream import exchange_code, get_discovery
from app.infra.db import session_scope

router = APIRouter()


def _pkce_challenge(verifier: str) -> str:
    digest = sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


async def db() -> AsyncIterator[AsyncSession]:
    async with session_scope() as session:
        yield session


@router.get("/.well-known/openid-configuration")
def openid_configuration() -> JSONResponse:
    settings = get_settings()
    return JSONResponse(
        {
            "issuer": settings.idp_issuer,
            "authorization_endpoint": f"{settings.idp_issuer}/authorize",
            "token_endpoint": f"{settings.idp_issuer}/token",
            "userinfo_endpoint": f"{settings.idp_issuer}/userinfo",
            "jwks_uri": f"{settings.idp_issuer}/jwks",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "scopes_supported": ["openid", "email", "profile"],
            "token_endpoint_auth_methods_supported": ["client_secret_post"],
            "code_challenge_methods_supported": ["S256"],
            "claims_supported": [
                "sub",
                "iss",
                "aud",
                "exp",
                "iat",
                "jti",
                "typ",
                "email",
                "name",
                "roles",
                "tenant_id",
                "upstream_idp",
                "upstream_sub",
            ],
        }
    )


@router.get("/jwks")
def jwks() -> JSONResponse:
    return JSONResponse(jwks_document())


class AuthorizeParams(BaseModel):
    client_id: str
    redirect_uri: str
    response_type: str
    scope: str = "openid email profile"
    state: str
    code_challenge: str | None = None
    code_challenge_method: str | None = None


@router.get("/authorize")
async def authorize(request: Request, db: AsyncSession = Depends(db)) -> RedirectResponse:
    settings = get_settings()
    p = AuthorizeParams.model_validate(dict(request.query_params))
    if p.client_id != settings.idp_client_id:
        raise HTTPException(status_code=400, detail="unknown client_id")
    if p.response_type != "code":
        raise HTTPException(status_code=400, detail="unsupported_response_type")

    # Our IdP's own code generation is backed by a federated login to the
    # upstream. We remember the downstream (bff) state/redirect_uri here.
    bff_state = p.state
    bff_redirect_uri = p.redirect_uri
    upstream_state = secrets.token_urlsafe(24)
    upstream_nonce = secrets.token_urlsafe(24)
    upstream_verifier = secrets.token_urlsafe(48)
    upstream_challenge = _pkce_challenge(upstream_verifier)
    return_to_payload = json.dumps(
        {"bff_state": bff_state, "bff_redirect_uri": bff_redirect_uri, "bff_client_id": p.client_id}
    )

    await db.execute(
        text(
            "INSERT INTO auth_states(state, nonce, code_verifier, return_to, expires_at) "
            "VALUES (:s, :n, :v, :rt, now() + interval '10 minutes')"
        ),
        {"s": upstream_state, "n": upstream_nonce, "v": upstream_verifier, "rt": return_to_payload},
    )

    discovery = await get_discovery()
    upstream_params = {
        "response_type": "code",
        "client_id": settings.oidc_upstream_client_id,
        "redirect_uri": f"{settings.idp_issuer}/auth/callback",
        "scope": "openid email profile",
        "state": upstream_state,
        "nonce": upstream_nonce,
        "code_challenge": upstream_challenge,
        "code_challenge_method": "S256",
    }
    return RedirectResponse(f"{discovery.authorization_endpoint}?{urlencode(upstream_params)}")


# In-memory storage of *downstream* codes (issued to the BFF). Short-lived; a
# horizontal scale-out would move this to a `codes` table. For dev it's fine.
_issued_codes: dict[str, dict[str, str | UpstreamIdentity]] = {}


@router.get("/auth/callback")
async def upstream_callback(
    code: str, state: str, db: AsyncSession = Depends(db)
) -> RedirectResponse:
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
    code_verifier, return_to_payload = hit
    rt = json.loads(return_to_payload)

    _, identity = await exchange_code(
        code=code,
        redirect_uri=f"{settings.idp_issuer}/auth/callback",
        code_verifier=code_verifier,
    )

    # Issue our own downstream code to the BFF.
    downstream_code = secrets.token_urlsafe(32)
    _issued_codes[downstream_code] = {
        "identity": identity,
        "expires_at": str(int(time.time()) + 60),
    }

    params = {"code": downstream_code, "state": rt["bff_state"]}
    return RedirectResponse(f"{rt['bff_redirect_uri']}?{urlencode(params)}")


@router.post("/token")
async def token(
    grant_type: str = Form(...),
    code: str | None = Form(None),
    refresh_token: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    client_id: str = Form(...),
    client_secret: str | None = Form(None),
) -> JSONResponse:
    settings = get_settings()
    if client_id != settings.idp_client_id or client_secret != settings.idp_client_secret:
        raise HTTPException(status_code=401, detail="invalid_client")

    if grant_type == "authorization_code":
        if code is None or code not in _issued_codes:
            raise HTTPException(status_code=400, detail="invalid_grant")
        entry = _issued_codes.pop(code)
        if int(entry["expires_at"]) < int(time.time()):  # type: ignore[arg-type]
            raise HTTPException(status_code=400, detail="expired_grant")
        identity = entry["identity"]
        if not isinstance(identity, UpstreamIdentity):
            raise HTTPException(status_code=500, detail="internal error")
        minted = mint_tokens(identity)
        return JSONResponse(
            {
                "token_type": "Bearer",
                "access_token": minted.access_token,
                "id_token": minted.id_token,
                "refresh_token": minted.refresh_token,
                "expires_in": settings.idp_access_token_ttl_seconds,
                "scope": "openid email profile",
            }
        )

    if grant_type == "refresh_token":
        if refresh_token is None:
            raise HTTPException(status_code=400, detail="invalid_request")
        try:
            claims = verify_token(refresh_token, expected_kind="refresh")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid_grant: {exc}") from exc
        identity = UpstreamIdentity(
            upstream_idp=str(claims.get("upstream_idp", "")),
            upstream_sub=str(claims.get("upstream_sub", "")),
            email=str(claims.get("email", "")),
            name=claims.get("name"),
            roles=list(claims.get("roles", [])),
            tenant_id=claims.get("tenant_id"),
        )
        minted = mint_tokens(identity)
        return JSONResponse(
            {
                "token_type": "Bearer",
                "access_token": minted.access_token,
                "id_token": minted.id_token,
                "refresh_token": minted.refresh_token,
                "expires_in": settings.idp_access_token_ttl_seconds,
                "scope": "openid email profile",
            }
        )

    raise HTTPException(status_code=400, detail="unsupported_grant_type")


@router.get("/userinfo")
def userinfo(request: Request) -> JSONResponse:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401)
    token = auth.split(" ", 1)[1]
    try:
        claims = verify_token(token, expected_kind="access")
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return JSONResponse(
        {
            "sub": claims["sub"],
            "email": claims.get("email"),
            "name": claims.get("name"),
            "roles": claims.get("roles", []),
            "tenant_id": claims.get("tenant_id"),
        }
    )
