"""Verify the BFF injects security headers on its own responses,
and skips the CSP on /dagster/* proxied paths."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_bff_root_has_security_headers(unauth_client: AsyncClient):
    """An unauthenticated request still gets a 401 — but the response
    must carry the security headers."""
    response = await unauth_client.get("/")
    # 401 or 200 or 302 — any response from the BFF should carry the headers.
    assert "X-Frame-Options" in response.headers
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in response.headers
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert "Referrer-Policy" in response.headers


@pytest.mark.integration
async def test_bff_dagster_path_skips_csp(viewer_client: AsyncClient):
    """The /dagster/* proxy paths get the other security headers but
    NOT our strict BFF CSP — the middleware does not override Dagster's own
    CSP (which uses nonces for its inline scripts)."""
    response = await viewer_client.get("/dagster/")
    # Either 200 (Dagster HTML) or 5xx (Dagster down) — assert headers behavior.
    assert response.headers.get("X-Frame-Options") == "DENY"
    # Our BFF CSP must NOT be injected; Dagster may ship its own nonce-based CSP.
    csp = response.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" not in csp
