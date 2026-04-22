"""Shared test fixtures."""

from __future__ import annotations

import os

import pytest

# Ensure settings that are required at import time are present for all tests.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://quant:quant@localhost:5433/quant")
os.environ.setdefault("SESSION_JWT_SIGNING_KEY", "test-key-not-for-production")
os.environ.setdefault(
    "BFF_TOKEN_ENCRYPTION_KEY_B64",
    "MDEyMzQ1Njc4OUFCQ0RFRjAxMjM0NTY3ODlBQkNERUY=",  # 32 bytes
)
os.environ.setdefault("BFF_SESSION_COOKIE_SECURE", "false")


@pytest.fixture(autouse=True)
async def clean_audit_log():
    """Truncate audit_log before each test to prevent row leakage between tests."""
    from app.infra.db import session_scope
    from sqlalchemy import text

    async with session_scope() as session:
        await session.execute(text("TRUNCATE TABLE audit_log RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture(autouse=True)
async def reset_db_engine():
    """Dispose the global engine after each test.

    Fresh engine per test because the global async engine binds to the event loop;
    reusing it across tests that may run in different loops causes connection errors.
    """
    yield
    from app.infra.db import dispose_engine

    await dispose_engine()
