"""Signing key management for the IdP role.

Dev: a fresh RSA keypair is generated on process start. Good enough because dev
sessions do not persist restarts.

Prod: the private key material is provided via the `IDP_SIGNING_KEY_B64` env var
(base64-encoded PEM) sourced from Secret Manager. Additional retired keys can be
published on /jwks during rotation windows; see the `signing_keys` Postgres table.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from functools import lru_cache

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import get_settings


def _b64url_uint(n: int) -> str:
    byte_len = (n.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(n.to_bytes(byte_len, "big")).rstrip(b"=").decode()


@dataclass(frozen=True)
class SigningKey:
    kid: str
    algorithm: str
    private_pem: str
    public_jwk: dict[str, str]


def _load_private_pem() -> str:
    settings = get_settings()
    if settings.idp_signing_key_b64:
        return base64.b64decode(settings.idp_signing_key_b64).decode()

    # Dev-only: generate an ephemeral keypair. Not persisted.
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


@lru_cache(maxsize=1)
def current_signing_key() -> SigningKey:
    settings = get_settings()
    pem = _load_private_pem()
    private_key = serialization.load_pem_private_key(pem.encode(), password=None)
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise RuntimeError("idp signing key must be RSA")
    public_numbers = private_key.public_key().public_numbers()
    return SigningKey(
        kid=settings.idp_signing_key_id,
        algorithm="RS256",
        private_pem=pem,
        public_jwk={
            "kty": "RSA",
            "kid": settings.idp_signing_key_id,
            "use": "sig",
            "alg": "RS256",
            "n": _b64url_uint(public_numbers.n),
            "e": _b64url_uint(public_numbers.e),
        },
    )


def jwks_document() -> dict[str, list[dict[str, str]]]:
    """Public JWKS. Includes the active key and any retiring keys tracked in DB.

    For dev, only the in-memory active key is returned. Prod can extend this
    with a DB query over `signing_keys` WHERE status IN ('active','retiring').
    """
    return {"keys": [current_signing_key().public_jwk]}
