"""AES-256-GCM envelope for tokens-at-rest in the sessions table.

Keys come from env (`BFF_TOKEN_ENCRYPTION_KEY_B64`). In prod the env var is sourced
from Secret Manager; in dev it lives in `.env.local`. No plaintext on disk ever.
"""

from __future__ import annotations

import base64
import os
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings


@lru_cache(maxsize=1)
def _key() -> AESGCM:
    raw = base64.b64decode(get_settings().bff_token_encryption_key_b64)
    if len(raw) not in (16, 24, 32):
        raise RuntimeError(
            "BFF_TOKEN_ENCRYPTION_KEY_B64 must decode to 16/24/32 bytes (AES-128/192/256)"
        )
    return AESGCM(raw)


def seal(plaintext: str, *, associated: bytes = b"") -> bytes:
    """Encrypt a string; returns nonce || ciphertext."""
    nonce = os.urandom(12)
    ct = _key().encrypt(nonce, plaintext.encode("utf-8"), associated or None)
    return nonce + ct


def open_(blob: bytes, *, associated: bytes = b"") -> str:
    """Decrypt a seal() output; returns the original string."""
    nonce, ct = blob[:12], blob[12:]
    return _key().decrypt(nonce, ct, associated or None).decode("utf-8")
