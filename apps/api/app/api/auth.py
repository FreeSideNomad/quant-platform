"""OIDC authentication endpoints.

Stub: the full OIDC flow (authlib + customer IdP + session JWT minting)
will replace these handlers. Sufficient for step 1 smoke tests.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter()


class AuthStatus(BaseModel):
    authenticated: bool
    provider_configured: bool


@router.get("/status", response_model=AuthStatus)
async def status() -> AuthStatus:
    settings = get_settings()
    return AuthStatus(
        authenticated=False,
        provider_configured=bool(settings.oidc_upstream_discovery_url),
    )
