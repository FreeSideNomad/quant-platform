"""Minimal OIDC-compatible provider for local development.

Implements the endpoints the IdP role's upstream client actually needs:
- /.well-known/openid-configuration
- /jwks.json
- /authorize              (presents a login form)
- /authorize/submit       (validates credentials, issues code, redirects)
- /token                  (code → tokens)
- /userinfo

Seeded users: `admin/admin` and `user/user`. Credentials hard-coded — this is
a mock. Do not deploy to prod.
"""

from __future__ import annotations

import secrets
import time
from typing import Any
from urllib.parse import urlencode

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

ISSUER = "http://mock-oidc:9800"
KID = "mock-oidc-dev-key"

USERS: dict[str, dict[str, Any]] = {
    "admin": {
        "password": "admin",
        "sub": "mock|admin",
        "email": "admin@example.test",
        "name": "Admin User",
        "roles": ["admin", "quant", "viewer"],
    },
    "user": {
        "password": "user",
        "sub": "mock|user",
        "email": "user@example.test",
        "name": "Regular User",
        "roles": ["quant", "viewer"],
    },
}

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_private_pem = _key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()
_public_numbers = _key.public_key().public_numbers()

_pending_authorize: dict[str, dict[str, Any]] = {}
_codes: dict[str, dict[str, Any]] = {}
_tokens: dict[str, dict[str, Any]] = {}


def _b64url_uint(n: int) -> str:
    from base64 import urlsafe_b64encode

    byte_len = (n.bit_length() + 7) // 8
    return urlsafe_b64encode(n.to_bytes(byte_len, "big")).rstrip(b"=").decode()


app = FastAPI(title="mock-oidc")


@app.get("/.well-known/openid-configuration")
def discovery() -> JSONResponse:
    return JSONResponse(
        {
            "issuer": ISSUER,
            "authorization_endpoint": f"{ISSUER}/authorize",
            "token_endpoint": f"{ISSUER}/token",
            "userinfo_endpoint": f"{ISSUER}/userinfo",
            "jwks_uri": f"{ISSUER}/jwks.json",
            "response_types_supported": ["code"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "scopes_supported": ["openid", "email", "profile"],
            "token_endpoint_auth_methods_supported": ["client_secret_post"],
            "claims_supported": ["sub", "email", "name", "roles"],
            "code_challenge_methods_supported": ["S256"],
        }
    )


@app.get("/jwks.json")
def jwks() -> JSONResponse:
    return JSONResponse(
        {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": KID,
                    "use": "sig",
                    "alg": "RS256",
                    "n": _b64url_uint(_public_numbers.n),
                    "e": _b64url_uint(_public_numbers.e),
                }
            ]
        }
    )


_LOGIN_FORM = """
<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><title>Mock IdP login</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#fafaf9;margin:0;padding:4rem;color:#201f1c}}
.card{{max-width:22rem;margin:0 auto;background:#fdfdfc;border:1px solid #dfdfdc;border-radius:4px;padding:1.5rem}}
h1{{font-size:1rem;font-weight:500;margin:0 0 0.25rem;color:#6f6e6a;letter-spacing:0.04em;text-transform:uppercase}}
.sub{{font-size:0.85rem;color:#6f6e6a;margin:0 0 1.25rem}}
label{{display:block;font-size:0.8rem;color:#6f6e6a;margin:0.75rem 0 0.25rem}}
input{{width:100%;padding:0.5rem 0.6rem;border:1px solid #dfdfdc;border-radius:4px;font-size:0.9rem;box-sizing:border-box}}
input:focus{{outline:none;border-color:#0b2545;box-shadow:0 0 0 3px rgba(11,37,69,0.15)}}
button{{margin-top:1.25rem;width:100%;padding:0.55rem;background:#0b2545;color:#fafafa;border:0;border-radius:4px;font-size:0.9rem;cursor:pointer}}
button:hover{{background:#091c37}}
.hint{{margin-top:1rem;font-size:0.75rem;color:#6f6e6a}}
code{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;background:#f2f2f0;padding:1px 4px;border-radius:2px}}
</style></head><body>
<div class="card">
<h1>Mock Identity Provider</h1>
<p class="sub">Development-only. Two seeded users available.</p>
<form method="post" action="/authorize/submit">
<input type="hidden" name="request_id" value="{request_id}">
<label>Username</label>
<input name="username" autofocus autocomplete="off">
<label>Password</label>
<input name="password" type="password" autocomplete="off">
<button type="submit">Sign in</button>
</form>
<p class="hint">Try <code>admin / admin</code> or <code>user / user</code>.</p>
</div></body></html>
"""


@app.get("/authorize", response_class=HTMLResponse)
def authorize(
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    response_type: str = Query(...),
    scope: str = Query("openid email profile"),
    state: str = Query(...),
    nonce: str | None = Query(None),
    code_challenge: str | None = Query(None),
    code_challenge_method: str | None = Query(None),
) -> HTMLResponse:
    if response_type != "code":
        raise HTTPException(400, detail="unsupported_response_type")
    request_id = secrets.token_urlsafe(24)
    _pending_authorize[request_id] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "created_at": int(time.time()),
    }
    return HTMLResponse(_LOGIN_FORM.format(request_id=request_id))


@app.post("/authorize/submit")
def authorize_submit(
    request_id: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
) -> RedirectResponse:
    pending = _pending_authorize.pop(request_id, None)
    if pending is None:
        raise HTTPException(400, detail="invalid_or_expired_request")
    user = USERS.get(username)
    if user is None or user["password"] != password:
        raise HTTPException(401, detail="invalid_credentials")

    code = secrets.token_urlsafe(24)
    _codes[code] = {
        "client_id": pending["client_id"],
        "redirect_uri": pending["redirect_uri"],
        "scope": pending["scope"],
        "nonce": pending.get("nonce"),
        "code_challenge": pending.get("code_challenge"),
        "code_challenge_method": pending.get("code_challenge_method"),
        "sub": user["sub"],
        "email": user["email"],
        "name": user["name"],
        "roles": user["roles"],
        "created_at": int(time.time()),
    }
    sep = "&" if "?" in pending["redirect_uri"] else "?"
    return RedirectResponse(
        f"{pending['redirect_uri']}{sep}{urlencode({'code': code, 'state': pending['state']})}",
        status_code=302,
    )


@app.post("/token")
def token(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str = Form(...),
    client_secret: str | None = Form(None),  # noqa: ARG001
    code_verifier: str | None = Form(None),
) -> JSONResponse:
    entry = _codes.pop(code, None)
    if entry is None or entry["client_id"] != client_id or entry["redirect_uri"] != redirect_uri:
        raise HTTPException(400, detail="invalid_grant")
    if grant_type != "authorization_code":
        raise HTTPException(400, detail="unsupported_grant_type")

    # Verify PKCE if it was requested.
    if entry.get("code_challenge"):
        from base64 import urlsafe_b64encode
        from hashlib import sha256

        if not code_verifier:
            raise HTTPException(400, detail="invalid_grant: missing code_verifier")
        derived = urlsafe_b64encode(sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
        if derived != entry["code_challenge"]:
            raise HTTPException(400, detail="invalid_grant: pkce_mismatch")

    now = int(time.time())
    id_token_claims = {
        "iss": ISSUER,
        "sub": entry["sub"],
        "aud": client_id,
        "exp": now + 3600,
        "iat": now,
        "nonce": entry.get("nonce"),
        "email": entry["email"],
        "name": entry["name"],
        "roles": entry["roles"],
    }
    id_token = jwt.encode(id_token_claims, _private_pem, algorithm="RS256", headers={"kid": KID})
    access_token = secrets.token_urlsafe(32)
    _tokens[access_token] = entry
    return JSONResponse(
        {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "id_token": id_token,
            "scope": entry["scope"],
        }
    )


@app.get("/userinfo")
def userinfo(request: Request) -> JSONResponse:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401)
    entry = _tokens.get(auth.split(" ", 1)[1])
    if entry is None:
        raise HTTPException(401)
    return JSONResponse(
        {
            "sub": entry["sub"],
            "email": entry["email"],
            "name": entry["name"],
            "roles": entry["roles"],
        }
    )
