"""Internal endpoints: health, readiness, PGMQ push delivery targets."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app import __version__
from app.config import get_settings
from app.infra.db import session_scope

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    role: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe. Does not touch external dependencies."""
    return HealthResponse(status="ok", role=get_settings().role.value, version=__version__)


@router.get("/ready", response_model=HealthResponse)
async def ready() -> HealthResponse:
    """Readiness probe. Verifies database is reachable."""
    async with session_scope() as session:
        await session.execute(text("SELECT 1"))
    return HealthResponse(status="ready", role=get_settings().role.value, version=__version__)
