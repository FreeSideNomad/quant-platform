"""Application entry point. Role selection happens here.

Running the process is:
    ROLE=api          uvicorn app.main:app
    ROLE=worker-proj-ui python -m app.workers.proj_ui
    ROLE=scheduler    python -m app.scheduler
    etc.

When imported by `uvicorn app.main:app`, this module exposes `app` — the
FastAPI ASGI application for the `api` role. Worker roles are run via
`python -m` on their own module and do not import this file.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.commands import router as commands_router
from app.api.internal import router as internal_router
from app.api.models import router as models_router
from app.api.queries import router as queries_router
from app.config import Role, get_settings
from app.infra.db import dispose_engine
from app.infra.logging import configure_logging, get_logger


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log = get_logger("app.main")
    settings = get_settings()
    log.info("api.starting", role=settings.role.value)
    try:
        yield
    finally:
        await dispose_engine()
        log.info("api.stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.role is not Role.api:
        # uvicorn was invoked on a non-api role; refuse to start the HTTP app.
        raise RuntimeError(
            f"ROLE={settings.role.value}: do not use uvicorn for this role; "
            f"run `python -m app.workers.{settings.role.value.replace('worker-', '')}` instead"
        )

    application = FastAPI(
        title="Quant Platform API",
        version="0.0.0",
        lifespan=lifespan,
    )
    application.include_router(internal_router, prefix="/internal", tags=["internal"])
    application.include_router(auth_router, prefix="/auth", tags=["auth"])
    application.include_router(commands_router, prefix="/commands", tags=["commands"])
    application.include_router(queries_router, prefix="/queries", tags=["queries"])
    application.include_router(models_router, tags=["models"])
    return application


# Configured at import time so that `uvicorn app.main:app` works directly.
# For non-api roles, the module is not imported this way.
app = create_app()
