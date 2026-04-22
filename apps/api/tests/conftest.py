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
# The API container (and the running IdP) use the external-facing issuer URL.
# Tokens minted locally must carry the same issuer so the live API can verify them.
os.environ.setdefault("IDP_ISSUER", "http://localhost:8001")
# Fixed dev signing key so tokens minted locally by test fixtures are verifiable by the
# live API container (which fetches the public key from the IdP's /jwks endpoint).
# The same key material is set on the `idp` service in docker-compose.yml.
os.environ.setdefault(
    "IDP_SIGNING_KEY_B64",
    "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSUV2Z0lCQURBTkJna3Foa2lHOXcwQkFRRUZBQVNDQktnd2dnU2tBZ0VBQW9JQkFRQzB6cVFQeFN6Y2VGbXEKZW02NWRYVEJpaG1kV2FSSlI0RjhqaUN0b1dCTk5TK3JyRHFkMWoydi9EeWJEbzBoTDNXTmcrTjUzZG5rM1BqdQpQUlhRUjE1alZOU0pZN1M5Rys5ZHUwMWI4UFZ4Q0dRK0EyOHFQTEh2alVrM1RZLzl0SHM2enZxQ3dpWnA4R1J3CnBublJTUTNxRE1zSFJVK09zOGFHc0hwNnM1YlNhMVRocFcySVh3aCtCNFNmUnE5ZXBMQk5rNXJ6OTN3TUVib0sKeEdabTF1bHd6VGZTd3Flc0Zha3l4ckRoUlgxWm5KTWRTNWxnYnN6T09zaEt0cnJ1emF2RnozZnNmbXJ2T2ZrdQpETWtwb1c5SFJ2ckJjRFQzTmZOelBQeVAvM0t5bDRBK0tsaWE2NFZXZEtKaTlLN0RrL3l5MHdlanlFbXk3WnlWCkc0c1BySllyQWdNQkFBRUNnZ0VBRXZSS3QxWFlveHJXdzR3UmlYaFZEMmtCSmNGYyswcjNaRzJvalZYZjQ1Z24KY1liSG42ankrZWVtYnRiZFYvK1lBakxlVTZDUjZXL1BoTXpRanU5bkVndGdPekJCcFVXRmJXZTg3MTR1VE1yYQp2MTdheTRHN1laS0gwZzFiMS9hUXFKU1pmR3NLc3pacFFSOU5TL0d0b2hOSjdCbUpyVHNPeDlYcEJtM3g2Z2hRCnJQT0JWendtRzJCcGFjN0wxZXhVUWFWYnZmSVZ4VDc3amF0bEovOUV2UXJUNWxlbWZoZWk5SlYvWmZacUYwTnQKaHRqdnZUVG8rQWFFOWxWbytQUU43NXlZVXB2bVBTS2duZ2tKTVJmb1licTlodE9Hejd1dE04WHlJa3AxUWJZZwpPdk1IVUZkNVRWSjFvMFFlbUZ3U0VjWGxucmttOEhPdU01M04rRTdyZ1FLQmdRRFhkTnBBNzNvR2VlZjJCNWRtCnY0SStpNFlQcDRsSURGNjdRV01BOEpXMHNYRnZPdVJBdGJzaXo0eDhhbDRMcUg0Ny9VUFYvandzOFpBZ0FzY3UKSW5SVGY5RWhwUUJXd1Y2Nlp1c3pLZDJHcUtMVFhFVXVLcHFDUVBGSCt2Qlh4TzJnYnZKRjZ5SURnVVRySFRRUgpCbnk4RmJyalI4ZDJOSWQvSEF3eDVIcW13UUtCZ1FEVzFLS1pDZEQvZi8rN0g5c1hna0FvK1htd0Z0MzVUS1FzCkx5NWtRVVBtRTVrMGtqakVrcnhvMStPZk51SVRrWW5mZEl3ZW5wL1lJU1hWR1k1U3F6OUtabEVjS3hkQk52cGsKaklUa1o3dm5rS2F3eUZ0TFBUNVF0bDdQeVhCekVocUg1TnZBN3Vka1VSUHV3THpDTUFGODd3V0NURG1tZStkegphWHYrYnJGRDZ3S0JnQkM0Y3MralJoY0drdWZYQXZyb1ZkVkF3ckNvVWRFVGxLNTNqcFZlRm1BbGZTWWlyZUFQCnVtd2pLMFhrZzFQb1NaT2lQZ2QzYVhnYmJ4SHM1VVJCVEVIR281WTIxZVhscjlKTGRtbE1FSE1JMTBvTDJScVMKRjllUDdxbWxZYzJON05zTWdTVEg4S1hRL0dZNnAvWENTUi9YbDk5WGpMVXhzbW84NVAxaU85cUJBb0dCQUlYMwpLejRMNVF5dklTWHJnNUJ4Wk5rb1dUMzV4SXBGeE1yWTBURXJrYy9Ud09JTG5PTFlMaTJqRXdxaUN2RHcvTzBmCm5KRXJrYm9SVWFwRnVYN0wwemZ0L2Y1MjBKV1dWeWFFaWdwMHRiUjllN1VaKy9RN1NMVEVSUE9HUmwwN21OZk4KVzB4QXJvTGNISFh5TXNOVmRGZ1lKWE5QWFZQNFNDaXNTdW9xMU5mcEFvR0JBSWJxSnZPSEN1Qk1jWU85WFZ2agpNcnJROWg5S0x0eWI0Sjh3VDcxeFpBb0V3VURtOE1WeHR0NU9iRHhqem8wRG96MU9LTnpBS2dYbXJoWDc1SjgyCnB5bFNCdjN6NzJpSFp5S2dKQ0hPZVllVmsvcVlUNWczcnp3V0VHYlRDODhSK0FoSHZQRzhXTXZ6ZWxtU1hZTEYKR0puYXpMZFh0TldueXVLTk5VRldTdW0zCi0tLS0tRU5EIFBSSVZBVEUgS0VZLS0tLS0K",
)


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


@pytest.fixture
def api_base_url() -> str:
    """Base URL for the API role. Override via API_BASE_URL env var."""
    return os.environ.get("API_BASE_URL", "http://localhost:8000")


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
    """AsyncClient with no auth targeting the BFF — suitable for testing 401 responses on BFF routes."""
    import httpx

    async with httpx.AsyncClient(base_url=bff_base_url) as client:
        yield client


@pytest.fixture
async def unauth_api_client(api_base_url: str):
    """AsyncClient with no auth targeting the API role directly — for testing 401 on Bearer-protected routes."""
    import httpx

    async with httpx.AsyncClient(base_url=api_base_url) as client:
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
async def viewer_bearer_client(api_base_url: str):
    """AsyncClient with Authorization: Bearer <viewer-JWT> targeting the API role directly."""
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
        base_url=api_base_url,
        headers={"Authorization": f"Bearer {minted.access_token}"},
    ) as client:
        yield client


@pytest.fixture
async def quant_bearer_client(api_base_url: str):
    """AsyncClient with Authorization: Bearer <quant-JWT> targeting the API role directly."""
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
        base_url=api_base_url,
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
