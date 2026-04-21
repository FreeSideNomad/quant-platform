"""JWT minting for the federation IdP."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization

from app.config import get_settings
from app.idp.keys import current_signing_key


@dataclass(frozen=True)
class UpstreamIdentity:
    """Verified identity returned by an upstream IdP after a successful login."""

    upstream_idp: str
    upstream_sub: str
    email: str
    name: str | None
    roles: list[str]
    tenant_id: str | None = None


@dataclass(frozen=True)
class MintedTokens:
    access_token: str
    id_token: str
    refresh_token: str
    access_expires_at: int
    refresh_expires_at: int


def _internal_sub(identity: UpstreamIdentity) -> str:
    # Stable internal id derived from upstream identity.
    return f"qp|{identity.upstream_idp}|{identity.upstream_sub}"


def _make_claims(identity: UpstreamIdentity, *, exp_seconds: int, kind: str) -> dict[str, Any]:
    settings = get_settings()
    now = int(time.time())
    return {
        "iss": settings.idp_issuer,
        "sub": _internal_sub(identity),
        "aud": settings.idp_token_audience,
        "iat": now,
        "nbf": now,
        "exp": now + exp_seconds,
        "jti": secrets.token_urlsafe(16),
        "typ": kind,
        "email": identity.email,
        "name": identity.name,
        "roles": identity.roles,
        "tenant_id": identity.tenant_id,
        "upstream_idp": identity.upstream_idp,
        "upstream_sub": identity.upstream_sub,
    }


def mint_tokens(identity: UpstreamIdentity) -> MintedTokens:
    settings = get_settings()
    key = current_signing_key()

    access_claims = _make_claims(
        identity, exp_seconds=settings.idp_access_token_ttl_seconds, kind="access"
    )
    id_claims = _make_claims(identity, exp_seconds=settings.idp_access_token_ttl_seconds, kind="id")
    refresh_claims = _make_claims(
        identity, exp_seconds=settings.idp_refresh_token_ttl_seconds, kind="refresh"
    )

    headers = {"kid": key.kid}
    access = jwt.encode(access_claims, key.private_pem, algorithm=key.algorithm, headers=headers)
    id_token = jwt.encode(id_claims, key.private_pem, algorithm=key.algorithm, headers=headers)
    refresh = jwt.encode(refresh_claims, key.private_pem, algorithm=key.algorithm, headers=headers)

    return MintedTokens(
        access_token=access,
        id_token=id_token,
        refresh_token=refresh,
        access_expires_at=int(access_claims["exp"]),
        refresh_expires_at=int(refresh_claims["exp"]),
    )


def verify_token(token: str, *, expected_kind: str | None = None) -> dict[str, Any]:
    """Verify a token signed by this IdP and return its claims.

    Callers should pass `expected_kind` ("access" / "id" / "refresh") to ensure
    the token is being used for its intended purpose.
    """
    settings = get_settings()
    key = current_signing_key()
    private = serialization.load_pem_private_key(key.private_pem.encode(), password=None)
    public_pem = private.public_key().public_bytes(  # type: ignore[union-attr]
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    claims = jwt.decode(
        token,
        public_pem,
        algorithms=[key.algorithm],
        audience=settings.idp_token_audience,
        issuer=settings.idp_issuer,
        options={"require": ["exp", "iat", "sub", "aud", "iss"]},
    )
    if expected_kind is not None and claims.get("typ") != expected_kind:
        raise jwt.InvalidTokenError(f"expected typ={expected_kind}, got {claims.get('typ')!r}")
    return claims
