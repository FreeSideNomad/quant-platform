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

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

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
    application.include_router(commands_router, prefix="/api/commands", tags=["commands"])
    application.include_router(queries_router, prefix="/api/queries", tags=["queries"])
    application.include_router(models_router, prefix="/api", tags=["models"])

    static_dir = Path(os.environ.get("STATIC_DIR", "/app/static"))
    index_html = static_dir / "index.html"
    if static_dir.is_dir() and index_html.is_file():
        # Hashed asset paths like /assets/index-abc.js
        assets_dir = static_dir / "assets"
        if assets_dir.is_dir():
            application.mount(
                "/assets",
                StaticFiles(directory=str(assets_dir)),
                name="spa-assets",
            )

        # SPA fallback: any 404 on a GET request for a non-API path returns
        # index.html so the client-side router handles it.
        @application.exception_handler(StarletteHTTPException)
        async def _spa_404_fallback(
            request: Request, exc: StarletteHTTPException
        ) -> JSONResponse | FileResponse:
            path = request.url.path
            if (
                exc.status_code == 404
                and request.method == "GET"
                and not path.startswith(("/api", "/internal", "/auth", "/assets", "/docs", "/openapi"))
            ):
                return FileResponse(str(index_html))
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    return application


app = create_app()
