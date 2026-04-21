"""Cookie helpers for the BFF role. Every security flag set correctly.

Production: `__Host-qp_session` with `Secure` unconditionally. The `__Host-`
prefix forces browsers to require Secure + Path=/ + no Domain attribute.

Integration/dev: when `BFF_SESSION_COOKIE_SECURE=false` (plain-HTTP localhost,
integration tests using `httpx` which refuses to send Secure cookies over
`http://`), we drop both the `__Host-` prefix and the `Secure` attribute. The
resulting cookie still has HttpOnly + SameSite=Lax + Path=/ — strong enough
for dev — and no test needs a TLS cert.
"""

from __future__ import annotations

from fastapi import Response

from app.config import get_settings

SECURE_SESSION_COOKIE_NAME = "__Host-qp_session"
INSECURE_SESSION_COOKIE_NAME = "qp_session"
CSRF_COOKIE_NAME = "qp_csrf"


def session_cookie_name() -> str:
    return (
        SECURE_SESSION_COOKIE_NAME
        if get_settings().bff_session_cookie_secure
        else INSECURE_SESSION_COOKIE_NAME
    )


def set_session_cookie(response: Response, session_id: str, *, max_age_seconds: int) -> None:
    secure = get_settings().bff_session_cookie_secure
    response.set_cookie(
        key=session_cookie_name(),
        value=session_id,
        max_age=max_age_seconds,
        path="/",
        secure=secure,
        httponly=True,
        samesite="lax",
    )


def set_csrf_cookie(response: Response, csrf_token: str, *, max_age_seconds: int) -> None:
    secure = get_settings().bff_session_cookie_secure
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=max_age_seconds,
        path="/",
        secure=secure,
        httponly=False,  # SPA reads this and echoes as X-CSRF-Token header
        samesite="lax",
    )


def clear_session_cookies(response: Response) -> None:
    secure = get_settings().bff_session_cookie_secure
    response.delete_cookie(session_cookie_name(), path="/", secure=secure, samesite="lax")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/", secure=secure, samesite="lax")


# Backward-compat alias used in tests.
SESSION_COOKIE_NAME = SECURE_SESSION_COOKIE_NAME
