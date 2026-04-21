"""Unit tests for the API's Bearer-token verification dependency.

We mint tokens with the real IdP signing key and assert the dependency
accepts them, then tamper with each claim to prove it rejects.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api import auth_deps
from app.api.auth_deps import AuthenticatedUser, get_current_user, requires_role
from app.idp.keys import current_signing_key
from app.idp.tokens import UpstreamIdentity, mint_tokens


@pytest.fixture
def id_admin() -> UpstreamIdentity:
    return UpstreamIdentity(
        upstream_idp="mock",
        upstream_sub="mock|admin",
        email="admin@example.test",
        name="Admin",
        roles=["admin", "quant", "viewer"],
        tenant_id="acme",
    )


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/me")
    async def me(
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> dict[str, object]:
        return {"sub": user.sub, "roles": user.roles}

    @app.get("/admin-only")
    async def admin_only(
        user: AuthenticatedUser = Depends(requires_role("admin")),
    ) -> dict[str, object]:
        return {"ok": True, "sub": user.sub}

    return app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Swap the JWKS client for a fixture that serves the in-process public key.

    This keeps the unit test hermetic — no idp role required.
    """
    key = current_signing_key()
    private = serialization.load_pem_private_key(key.private_pem.encode(), password=None)
    public_pem = private.public_key().public_bytes(  # type: ignore[union-attr]
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    class _FakeSigningKey:
        key = public_pem

    def _fake_get_signing_key(_token: str) -> _FakeSigningKey:
        return _FakeSigningKey()

    monkeypatch.setattr(auth_deps, "_get_signing_key", _fake_get_signing_key)
    return TestClient(_build_app())


@pytest.mark.unit
def test_valid_token_authorises_request(client: TestClient, id_admin: UpstreamIdentity) -> None:
    tokens = mint_tokens(id_admin)
    resp = client.get("/me", headers={"authorization": f"Bearer {tokens.access_token}"})
    assert resp.status_code == 200
    assert resp.json()["roles"] == ["admin", "quant", "viewer"]


@pytest.mark.unit
def test_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.get("/me")
    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate", "").startswith("Bearer")


@pytest.mark.unit
def test_refresh_token_rejected_as_access(client: TestClient, id_admin: UpstreamIdentity) -> None:
    tokens = mint_tokens(id_admin)
    resp = client.get("/me", headers={"authorization": f"Bearer {tokens.refresh_token}"})
    assert resp.status_code == 401


@pytest.mark.unit
def test_tampered_token_rejected(client: TestClient, id_admin: UpstreamIdentity) -> None:
    tokens = mint_tokens(id_admin)
    parts = tokens.access_token.split(".")
    parts[1] = parts[1][:-1] + ("A" if parts[1][-1] != "A" else "B")
    tampered = ".".join(parts)
    resp = client.get("/me", headers={"authorization": f"Bearer {tampered}"})
    assert resp.status_code == 401


@pytest.mark.unit
def test_role_guard_allows_admin(client: TestClient, id_admin: UpstreamIdentity) -> None:
    tokens = mint_tokens(id_admin)
    resp = client.get("/admin-only", headers={"authorization": f"Bearer {tokens.access_token}"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.unit
def test_role_guard_rejects_non_admin(client: TestClient) -> None:
    user_only = UpstreamIdentity(
        upstream_idp="mock",
        upstream_sub="mock|user",
        email="user@example.test",
        name="User",
        roles=["quant", "viewer"],
        tenant_id="acme",
    )
    tokens = mint_tokens(user_only)
    resp = client.get("/admin-only", headers={"authorization": f"Bearer {tokens.access_token}"})
    assert resp.status_code == 403


@pytest.mark.unit
def test_alg_none_rejected(client: TestClient) -> None:
    """An attacker flipping the header alg to none must not verify."""
    header = {"alg": "none", "typ": "JWT", "kid": current_signing_key().kid}
    payload: dict[str, Any] = {
        "iss": "http://idp:8001",
        "sub": "qp|mock|admin",
        "aud": "quant-platform",
        "iat": 0,
        "exp": 9999999999,
        "typ": "access",
        "roles": ["admin"],
    }

    def b64(d: bytes) -> str:
        return base64.urlsafe_b64encode(d).rstrip(b"=").decode()

    bad = f"{b64(json.dumps(header).encode())}.{b64(json.dumps(payload).encode())}."
    resp = client.get("/me", headers={"authorization": f"Bearer {bad}"})
    assert resp.status_code == 401
