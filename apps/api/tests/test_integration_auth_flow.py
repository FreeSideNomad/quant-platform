"""End-to-end integration test: browser → bff → idp → mock-oidc and back.

Exercises the entire auth stack running under docker-compose. Requires:
  - `make dev && make migrate` has been run
  - The BFF is configured with BFF_SESSION_COOKIE_SECURE=false for http-on-localhost
    (docker-compose for local dev sets this); in that mode the cookie name is
    `qp_session` without the __Host- prefix.

Run: pytest -m integration tests/test_integration_auth_flow.py -q
"""

from __future__ import annotations

import asyncio
import re

import httpx
import pytest

BFF_URL = "http://localhost:8080"
IDP_URL = "http://localhost:8001"
MOCK_URL = "http://localhost:9800"

SESSION_COOKIE_CANDIDATES = ("__Host-qp_session", "qp_session")


def _any_session_cookie(cookies: list[str]) -> str | None:
    for c in cookies:
        for name in SESSION_COOKIE_CANDIDATES:
            if c.startswith(f"{name}="):
                return name
    return None


async def _login(client: httpx.AsyncClient, username: str, password: str) -> httpx.Response:
    """Drive the full login redirect chain. Returns the BFF callback response."""
    resp = await client.get(f"{BFF_URL}/auth/login", params={"return_to": "/auth/me"})
    assert resp.is_redirect, (resp.status_code, resp.text)
    resp = await client.get(resp.headers["location"])  # idp /authorize
    assert resp.is_redirect, (resp.status_code, resp.text)
    resp = await client.get(resp.headers["location"])  # mock /authorize (html form)
    assert resp.status_code == httpx.codes.OK
    match = re.search(r'name="request_id"\s+value="([^"]+)"', resp.text)
    assert match, "request_id missing from mock form"
    request_id = match.group(1)

    resp = await client.post(
        f"{MOCK_URL}/authorize/submit",
        data={"request_id": request_id, "username": username, "password": password},
    )
    assert resp.is_redirect, (resp.status_code, resp.text)
    resp = await client.get(resp.headers["location"])  # idp /auth/callback
    assert resp.is_redirect, (resp.status_code, resp.text)
    resp = await client.get(resp.headers["location"])  # bff /auth/callback
    return resp


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_auth_flow_admin_user() -> None:
    async with httpx.AsyncClient(follow_redirects=False, timeout=15.0) as client:
        # 1. Unauthenticated → 401 on /auth/me
        resp = await client.get(f"{BFF_URL}/auth/me")
        assert resp.status_code == httpx.codes.UNAUTHORIZED

        # 2-7. Full redirect chain
        resp = await _login(client, "admin", "admin")
        assert resp.is_redirect, (resp.status_code, resp.text)
        assert resp.headers["location"] == "/auth/me"

        set_cookies = resp.headers.get_list("set-cookie")
        session_cookie_name = _any_session_cookie(set_cookies)
        assert session_cookie_name, f"no session cookie found in {set_cookies}"
        session_ck = next(c for c in set_cookies if c.startswith(f"{session_cookie_name}="))
        csrf_ck = next(c for c in set_cookies if c.startswith("qp_csrf="))
        assert "HttpOnly" in session_ck
        assert "HttpOnly" not in csrf_ck
        assert "samesite=lax" in session_ck.lower()

        # 8. /auth/me with the session cookie returns the user
        resp = await client.get(f"{BFF_URL}/auth/me")
        assert resp.status_code == httpx.codes.OK, resp.text
        me = resp.json()
        assert me["email"] == "admin@example.test"
        assert "admin" in me["roles"]
        assert "quant" in me["roles"]

        # 9. CSRF-protected POST without header → 403
        resp = await client.post(f"{BFF_URL}/api/commands/ping", json={"message": "hello csrf"})
        assert resp.status_code == httpx.codes.FORBIDDEN

        # 10. Same POST with X-CSRF-Token echoed from cookie → 200
        csrf_token = client.cookies.get("qp_csrf")
        assert csrf_token
        resp = await client.post(
            f"{BFF_URL}/api/commands/ping",
            json={"message": "hello csrf"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == httpx.codes.OK, resp.text
        event_id = resp.json()["event_id"]

        # 11. Projector is running; wait briefly then query for our ping.
        await asyncio.sleep(2.0)
        resp = await client.get(f"{BFF_URL}/api/queries/pings")
        assert resp.status_code == httpx.codes.OK
        pings = resp.json()
        assert any(p["event_id"] == event_id for p in pings), pings

        # 12. Logout revokes session; follow-up /auth/me → 401
        resp = await client.post(f"{BFF_URL}/auth/logout")
        assert resp.is_redirect, (resp.status_code, resp.text)
        client.cookies.clear()  # simulate the browser dropping the cookie
        resp = await client.get(f"{BFF_URL}/auth/me")
        assert resp.status_code == httpx.codes.UNAUTHORIZED


@pytest.mark.integration
@pytest.mark.asyncio
async def test_role_guard_user_has_only_quant_roles() -> None:
    """The `user/user` seeded account must not carry the admin role."""
    async with httpx.AsyncClient(follow_redirects=False, timeout=15.0) as client:
        resp = await _login(client, "user", "user")
        assert resp.is_redirect, (resp.status_code, resp.text)

        resp = await client.get(f"{BFF_URL}/auth/me")
        assert resp.status_code == httpx.codes.OK
        me = resp.json()
        assert me["email"] == "user@example.test"
        assert set(me["roles"]) == {"quant", "viewer"}
