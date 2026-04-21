"""Shared test fixtures."""

from __future__ import annotations

import os

# Ensure settings that are required at import time are present for all tests.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://quant:test@localhost:5433/quant")
os.environ.setdefault("SESSION_JWT_SIGNING_KEY", "test-key-not-for-production")
os.environ.setdefault(
    "BFF_TOKEN_ENCRYPTION_KEY_B64",
    "MDEyMzQ1Njc4OUFCQ0RFRjAxMjM0NTY3ODlBQkNERUY=",  # 32 bytes
)
os.environ.setdefault("BFF_SESSION_COOKIE_SECURE", "false")
