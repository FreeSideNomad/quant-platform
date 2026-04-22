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


# ---------------------------------------------------------------------------
# Role-based HTTP client fixtures (Task 1.5.0)
# ---------------------------------------------------------------------------


@pytest.fixture
def bff_base_url() -> str:
    """Base URL for the BFF service. Override via BFF_BASE_URL env var."""
    return os.environ.get("BFF_BASE_URL", "http://localhost:8080")


async def _make_session_cookie(roles: list[str], email: str, name: str) -> str:
    """Create a real BFF session in Postgres and return the raw cookie string."""
    from datetime import UTC, datetime, timedelta

    import httpx

    from app.bff.cookies import session_cookie_name
    from app.bff.sessions import create_session
    from app.idp.tokens import UpstreamIdentity, mint_tokens
    from app.infra.db import session_scope

    identity = UpstreamIdentity(
        upstream_idp="mock",
        upstream_sub=email,
        email=email,
        name=name,
        roles=roles,
        tenant_id=None,
    )
    minted = mint_tokens(identity)
    access_expires_at = datetime.fromtimestamp(minted.access_expires_at, tz=UTC)
    refresh_expires_at = datetime.fromtimestamp(minted.refresh_expires_at, tz=UTC)

    async with session_scope() as db_session:
        record = await create_session(
            db_session,
            user_sub=f"qp|mock|{email}",
            user_email=email,
            user_name=name,
            roles=roles,
            tenant_id=None,
            upstream_idp="mock",
            upstream_sub=email,
            id_token=minted.id_token,
            access_token=minted.access_token,
            refresh_token=minted.refresh_token,
            access_expires_at=access_expires_at,
            refresh_expires_at=refresh_expires_at,
            ip="127.0.0.1",
            user_agent="pytest",
        )

    cookie_name = session_cookie_name()
    return f"{cookie_name}={record.id}"


@pytest.fixture
async def unauth_client(bff_base_url: str):
    """AsyncClient with no auth — suitable for testing 401 responses."""
    import httpx

    async with httpx.AsyncClient(base_url=bff_base_url) as client:
        yield client


@pytest.fixture
async def viewer_client(bff_base_url: str):
    """AsyncClient authenticated as a viewer-role user via session cookie."""
    import httpx

    from app.bff.cookies import session_cookie_name

    raw_cookie = await _make_session_cookie(
        roles=["viewer"],
        email="viewer@test.local",
        name="Test Viewer",
    )
    cookie_name, _, cookie_value = raw_cookie.partition("=")
    async with httpx.AsyncClient(
        base_url=bff_base_url,
        cookies={cookie_name: cookie_value},
    ) as client:
        yield client


@pytest.fixture
async def quant_client(bff_base_url: str):
    """AsyncClient authenticated as a quant-role user via session cookie."""
    import httpx

    raw_cookie = await _make_session_cookie(
        roles=["quant"],
        email="quant@test.local",
        name="Test Quant",
    )
    cookie_name, _, cookie_value = raw_cookie.partition("=")
    async with httpx.AsyncClient(
        base_url=bff_base_url,
        cookies={cookie_name: cookie_value},
    ) as client:
        yield client


@pytest.fixture
async def viewer_bearer_client(bff_base_url: str):
    """AsyncClient with Authorization: Bearer <viewer-JWT>."""
    import httpx

    from app.idp.tokens import UpstreamIdentity, mint_tokens

    identity = UpstreamIdentity(
        upstream_idp="mock",
        upstream_sub="viewer@test.local",
        email="viewer@test.local",
        name="Test Viewer",
        roles=["viewer"],
        tenant_id=None,
    )
    minted = mint_tokens(identity)
    async with httpx.AsyncClient(
        base_url=bff_base_url,
        headers={"Authorization": f"Bearer {minted.access_token}"},
    ) as client:
        yield client


@pytest.fixture
async def quant_bearer_client(bff_base_url: str):
    """AsyncClient with Authorization: Bearer <quant-JWT>."""
    import httpx

    from app.idp.tokens import UpstreamIdentity, mint_tokens

    identity = UpstreamIdentity(
        upstream_idp="mock",
        upstream_sub="quant@test.local",
        email="quant@test.local",
        name="Test Quant",
        roles=["quant"],
        tenant_id=None,
    )
    minted = mint_tokens(identity)
    async with httpx.AsyncClient(
        base_url=bff_base_url,
        headers={"Authorization": f"Bearer {minted.access_token}"},
    ) as client:
        yield client


@pytest.fixture
async def quant_session_cookie(bff_base_url: str) -> str:
    """Raw 'name=value' session cookie string for the quant role.

    Used by WebSocket tests that build their own client and need to inject
    the cookie manually.
    """
    return await _make_session_cookie(
        roles=["quant"],
        email="quant-ws@test.local",
        name="Test Quant WS",
    )
