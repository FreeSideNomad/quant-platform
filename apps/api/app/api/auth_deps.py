"""API-side authentication dependencies.

The `api` role trusts tokens signed by our own IdP, verified against its JWKS.
The BFF attaches a Bearer token on every proxied request; this module verifies
it, extracts the claims, and exposes a `get_current_user` FastAPI dependency.

In-process JWKS cache refreshes on unknown `kid` (key rotation), otherwise the
public key is read once per process.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt import PyJWK, PyJWKClient, PyJWKClientError

from app.config import get_settings


@dataclass(frozen=True)
class AuthenticatedUser:
    sub: str
    email: str
    name: str | None
    roles: list[str]
    tenant_id: str | None
    raw: dict[str, Any]

    def has_role(self, role: str) -> bool:
        return role in self.roles


_jwks_client: PyJWKClient | None = None
_jwks_fetched_at: float = 0.0
_JWKS_MIN_REFETCH_SECONDS = 30.0


def _jwks_uri() -> str:
    settings = get_settings()
    # Internal URL is preferred in-cluster; the external issuer URL works for
    # tokens minted by an IdP on a different host.
    return f"{settings.idp_internal_url}/jwks"


def _jwks() -> PyJWKClient:
    global _jwks_client, _jwks_fetched_at
    if _jwks_client is None:
        _jwks_client = PyJWKClient(_jwks_uri(), cache_keys=True, lifespan=300)
        _jwks_fetched_at = time.monotonic()
    return _jwks_client


def _get_signing_key(token: str) -> PyJWK:
    """Try the cached JWKS; if the `kid` is unknown, refetch once (rotation)."""
    global _jwks_client, _jwks_fetched_at
    try:
        return _jwks().get_signing_key_from_jwt(token)
    except PyJWKClientError:
        now = time.monotonic()
        if now - _jwks_fetched_at < _JWKS_MIN_REFETCH_SECONDS:
            raise
        _jwks_client = None
        _jwks_fetched_at = 0.0
        return _jwks().get_signing_key_from_jwt(token)


def _verify_bearer(token: str) -> dict[str, Any]:
    settings = get_settings()
    key = _get_signing_key(token).key
    claims = jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=settings.idp_token_audience,
        issuer=settings.idp_issuer,
        options={"require": ["exp", "iat", "sub", "aud", "iss"]},
    )
    if claims.get("typ") not in ("access", None):
        raise jwt.InvalidTokenError(
            f"token type {claims.get('typ')!r} is not usable as an access token"
        )
    return claims


async def get_current_user(request: Request) -> AuthenticatedUser:
    """Extract the current user from a valid Bearer access token.

    Requests that reach the `api` role are expected to come through the BFF
    (which attaches the Authorization header). Unauthenticated direct calls
    return 401.
    """
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_bearer_token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth.split(" ", 1)[1]
    try:
        claims = _verify_bearer(token)
    except (jwt.InvalidTokenError, PyJWKClientError, httpx.HTTPError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid_token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    roles = claims.get("roles") or []
    if not isinstance(roles, list):
        roles = []
    return AuthenticatedUser(
        sub=str(claims["sub"]),
        email=str(claims.get("email", "")),
        name=claims.get("name"),
        roles=[str(r) for r in roles],
        tenant_id=claims.get("tenant_id"),
        raw=claims,
    )


def requires_role(*required: str):
    """FastAPI dependency factory: assert the current user has any of the given roles."""

    async def _guard(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if not any(user.has_role(r) for r in required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"requires one of roles: {', '.join(required)}",
            )
        return user

    return _guard
