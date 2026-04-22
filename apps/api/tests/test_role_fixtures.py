"""Smoke test: every role-based fixture is importable and correctly wired.

These fixtures are consumed by tests/test_dagster_proxy.py (cookie clients,
quant_session_cookie, bff_base_url) and tests/test_dagster_graphql_api.py
(Bearer clients). The smoke test keeps them honest by asserting the cookie
or Authorization header is actually attached to a trivial request and that
the local BFF/IdP plumbing accepts it.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_bff_base_url_is_string(bff_base_url: str):
    assert isinstance(bff_base_url, str)
    assert bff_base_url.startswith("http://") or bff_base_url.startswith("https://")


@pytest.mark.integration
async def test_unauth_client_has_no_cookies_or_auth_header(unauth_client: AsyncClient):
    assert dict(unauth_client.cookies) == {}
    assert "authorization" not in {k.lower() for k in unauth_client.headers}
    response = await unauth_client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.integration
async def test_viewer_client_carries_session_cookie(viewer_client: AsyncClient):
    from app.bff.cookies import session_cookie_name

    assert viewer_client.cookies.get(session_cookie_name())
    response = await viewer_client.get("/auth/me")
    assert response.status_code == 200
    assert "viewer" in response.json()["roles"]


@pytest.mark.integration
async def test_quant_client_carries_session_cookie(quant_client: AsyncClient):
    from app.bff.cookies import session_cookie_name

    assert quant_client.cookies.get(session_cookie_name())
    response = await quant_client.get("/auth/me")
    assert response.status_code == 200
    assert "quant" in response.json()["roles"]


@pytest.mark.integration
async def test_viewer_bearer_client_carries_authorization(viewer_bearer_client: AsyncClient):
    import jwt

    auth = viewer_bearer_client.headers.get("authorization", "")
    assert auth.startswith("Bearer ")
    token = auth.removeprefix("Bearer ")
    claims = jwt.decode(token, options={"verify_signature": False})
    assert "viewer" in claims["roles"]


@pytest.mark.integration
async def test_quant_bearer_client_carries_authorization(quant_bearer_client: AsyncClient):
    import jwt

    auth = quant_bearer_client.headers.get("authorization", "")
    assert auth.startswith("Bearer ")
    token = auth.removeprefix("Bearer ")
    claims = jwt.decode(token, options={"verify_signature": False})
    assert "quant" in claims["roles"]


@pytest.mark.integration
async def test_quant_session_cookie_is_raw_cookie_value(quant_session_cookie: str):
    assert "=" in quant_session_cookie
    name, _, value = quant_session_cookie.partition("=")
    assert name and value
