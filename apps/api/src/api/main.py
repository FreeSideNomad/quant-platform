"""FastAPI application entry point."""
from __future__ import annotations

from fastapi import FastAPI

from api import __version__
from api.settings import get_settings

settings = get_settings()

app = FastAPI(
    title="Quant Platform API",
    version=__version__,
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness + readiness probe."""
    return {
        "status": "ok",
        "role": settings.service_role,
        "version": __version__,
    }
