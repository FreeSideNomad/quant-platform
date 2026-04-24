from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Mock OIDC (M1 placeholder)")


@app.get("/.well-known/openid-configuration")
def openid_configuration() -> dict[str, str]:
    """Minimal OIDC discovery document — enough to pass a healthcheck."""
    return {
        "issuer": "http://localhost:14444",
        "authorization_endpoint": "http://localhost:14444/authorize",
        "token_endpoint": "http://localhost:14444/token",
        "jwks_uri": "http://localhost:14444/jwks",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
