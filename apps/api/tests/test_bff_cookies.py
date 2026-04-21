"""Unit tests for BFF cookies — every security flag asserted.

Two modes:
 - secure=true (prod) → __Host-qp_session with Secure
 - secure=false (dev/CI over plain HTTP) → qp_session without Secure
"""

from __future__ import annotations

import collections.abc

import pytest
from fastapi import Response

from app import config as _cfg
from app.bff.cookies import (
    CSRF_COOKIE_NAME,
    INSECURE_SESSION_COOKIE_NAME,
    SECURE_SESSION_COOKIE_NAME,
    clear_session_cookies,
    set_csrf_cookie,
    set_session_cookie,
)


def _parse_set_cookie(header: str) -> dict[str, str]:
    parts = [p.strip() for p in header.split(";")]
    name, value = parts[0].split("=", 1)
    out: dict[str, str] = {"__name": name, "__value": value}
    for attr in parts[1:]:
        if "=" in attr:
            k, v = attr.split("=", 1)
            out[k.lower()] = v
        else:
            out[attr.lower()] = "true"
    return out


def _headers_of(response: Response) -> list[str]:
    return [v.decode() for n, v in response.raw_headers if n == b"set-cookie"]


def _header_for(response: Response, cookie_name: str) -> str:
    for header in _headers_of(response):
        if header.startswith(f"{cookie_name}="):
            return header
    raise AssertionError(f"no Set-Cookie for {cookie_name}")


@pytest.fixture(autouse=True)
def _reset_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> collections.abc.Iterator[None]:
    # Force the insecure-prefix cookie variant by default (tests mirror CI/dev)
    monkeypatch.setenv("BFF_SESSION_COOKIE_SECURE", "false")
    _cfg._settings = None  # type: ignore[attr-defined]
    yield
    _cfg._settings = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_insecure_mode_uses_qp_session_without_host_prefix() -> None:
    response = Response()
    set_session_cookie(response, "sid-abc", max_age_seconds=3600)
    header = _header_for(response, INSECURE_SESSION_COOKIE_NAME)
    attrs = _parse_set_cookie(header)
    assert attrs["__name"] == "qp_session"
    assert attrs["__value"] == "sid-abc"
    assert attrs["httponly"] == "true"
    assert attrs["path"] == "/"
    assert attrs.get("samesite", "").lower() == "lax"
    assert "secure" not in attrs
    assert "domain" not in attrs


@pytest.mark.unit
def test_secure_mode_uses_host_prefix_and_secure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BFF_SESSION_COOKIE_SECURE", "true")
    _cfg._settings = None  # type: ignore[attr-defined]
    response = Response()
    set_session_cookie(response, "sid-xyz", max_age_seconds=3600)
    header = _header_for(response, SECURE_SESSION_COOKIE_NAME)
    attrs = _parse_set_cookie(header)
    assert attrs["__name"] == "__Host-qp_session"
    assert attrs["httponly"] == "true"
    assert attrs["path"] == "/"
    assert attrs.get("samesite", "").lower() == "lax"
    assert "secure" in attrs
    assert "domain" not in attrs
    assert attrs["max-age"] == "3600"


@pytest.mark.unit
def test_csrf_cookie_readable_by_spa() -> None:
    response = Response()
    set_csrf_cookie(response, "csrf-token-abc", max_age_seconds=3600)
    header = _header_for(response, CSRF_COOKIE_NAME)
    attrs = _parse_set_cookie(header)
    assert attrs["__name"] == "qp_csrf"
    # Deliberately NOT HttpOnly so the SPA can read it and echo as X-CSRF-Token.
    assert "httponly" not in attrs
    assert attrs["path"] == "/"
    assert attrs.get("samesite", "").lower() == "lax"


@pytest.mark.unit
def test_clear_session_cookies_removes_both() -> None:
    response = Response()
    clear_session_cookies(response)
    headers = _headers_of(response)
    assert any("qp_session" in h or "__Host-qp_session" in h for h in headers)
    assert any("qp_csrf" in h for h in headers)
    # Max-Age should be 0 (or expiry in the past) to signal deletion.
    for h in headers:
        attrs = _parse_set_cookie(h)
        assert attrs.get("max-age") in {"0", None} or "expires" in attrs
