"""Upstream OIDC federation — verifies id_tokens from mock/Google/Entra and
returns a canonical UpstreamIdentity for the IdP to mint our tokens from.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

import httpx
import jwt
from jwt import PyJWKClient

from app.config import get_settings
from app.idp.tokens import UpstreamIdentity


@dataclass
class OIDCDiscovery:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    userinfo_endpoint: str | None


_discovery_cache: OIDCDiscovery | None = None
_jwks_client: PyJWKClient | None = None


def _rewrite_host(url: str, new_base: str) -> str:
    """Prepend `new_base` (scheme+host+optional path) before the URL's path.

    Example: `_rewrite_host("http://mock-oidc:9800/authorize", "https://x.y/mock")`
    returns `"https://x.y/mock/authorize"`.
    """
    parsed = urlparse(url)
    base = urlparse(new_base)
    base_path = base.path.rstrip("/")
    return urlunparse(
        (
            base.scheme or parsed.scheme,
            base.netloc or parsed.netloc,
            f"{base_path}{parsed.path}",
            "",
            parsed.query,
            "",
        )
    )


async def get_discovery() -> OIDCDiscovery:
    global _discovery_cache
    if _discovery_cache is not None:
        return _discovery_cache
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(settings.oidc_upstream_discovery_url)
        resp.raise_for_status()
        doc = resp.json()

    authorization_endpoint = doc["authorization_endpoint"]
    if settings.oidc_upstream_browser_base:
        # Rewrite only the browser-facing endpoint; token endpoint stays
        # on the internal hostname used for server-to-server calls.
        authorization_endpoint = _rewrite_host(
            authorization_endpoint, settings.oidc_upstream_browser_base
        )

    _discovery_cache = OIDCDiscovery(
        issuer=doc["issuer"],
        authorization_endpoint=authorization_endpoint,
        token_endpoint=doc["token_endpoint"],
        jwks_uri=doc["jwks_uri"],
        userinfo_endpoint=doc.get("userinfo_endpoint"),
    )
    return _discovery_cache


def _jwks() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        assert _discovery_cache is not None, "call get_discovery() first"
        _jwks_client = PyJWKClient(_discovery_cache.jwks_uri)
    return _jwks_client


async def exchange_code(
    *, code: str, redirect_uri: str, code_verifier: str
) -> tuple[dict[str, str], UpstreamIdentity]:
    """Exchange auth code for tokens at the upstream, verify id_token, and
    return (raw-token-response, canonical identity).
    """
    settings = get_settings()
    discovery = await get_discovery()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            discovery.token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": settings.oidc_upstream_client_id,
                "client_secret": settings.oidc_upstream_client_secret,
                "code_verifier": code_verifier,
            },
        )
        resp.raise_for_status()
        tokens: dict[str, str] = resp.json()

    id_token = tokens["id_token"]
    signing_key = _jwks().get_signing_key_from_jwt(id_token).key
    claims = jwt.decode(
        id_token,
        signing_key,
        algorithms=["RS256"],
        audience=settings.oidc_upstream_client_id,
        issuer=discovery.issuer,
        options={"require": ["exp", "iat", "sub", "aud", "iss"]},
    )

    roles = claims.get("roles")
    if isinstance(roles, str):
        try:
            roles = json.loads(roles)
        except json.JSONDecodeError:
            roles = [r.strip() for r in roles.split(",") if r.strip()]
    if not isinstance(roles, list):
        roles = []

    identity = UpstreamIdentity(
        upstream_idp=settings.oidc_upstream_name,
        upstream_sub=str(claims["sub"]),
        email=str(claims.get("email", "")),
        name=claims.get("name"),
        roles=[str(r) for r in roles],
        tenant_id=None,  # single-tenant silo; filled by a later mapping step if needed
    )
    return tokens, identity
