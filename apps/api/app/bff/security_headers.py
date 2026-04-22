"""Security headers middleware for the BFF role.

Injects CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy,
and HSTS (when serving over HTTPS) on every BFF response. The /dagster/*
proxied paths get a relaxed CSP (Dagster ships its own inline JS that
violates a strict policy) — the proxy passes Dagster's headers through.
"""

from __future__ import annotations

from typing import Any, Callable

from starlette.types import ASGIApp, Receive, Scope, Send


_DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "connect-src 'self' ws: wss:; "
    "img-src 'self' data:; "
    "frame-ancestors 'none'"
)


class SecurityHeadersMiddleware:
    """Pure ASGI middleware — avoids BaseHTTPMiddleware's streaming/exception caveats."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        scheme: str = scope.get("scheme", "http")
        is_dagster = path.startswith("/dagster/") or path == "/dagster"
        is_https = scheme == "https"

        async def send_with_headers(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                # Avoid duplicating headers already set by the upstream response.
                existing = {k.lower() for k, _ in headers}

                def _add(name: str, value: str) -> None:
                    if name.lower().encode() not in existing:
                        headers.append((name.encode(), value.encode()))
                        existing.add(name.lower().encode())

                if not is_dagster and b"content-security-policy" not in existing:
                    headers.append((b"content-security-policy", _DEFAULT_CSP.encode()))
                _add("X-Frame-Options", "DENY")
                _add("X-Content-Type-Options", "nosniff")
                _add("Referrer-Policy", "strict-origin-when-cross-origin")
                if is_https:
                    _add("Strict-Transport-Security", "max-age=31536000")

                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)
