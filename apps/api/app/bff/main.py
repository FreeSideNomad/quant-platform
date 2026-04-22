"""FastAPI application for the `bff` role."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.bff.dagster_proxy import router as dagster_proxy_router
from app.bff.routes import router as bff_router
from app.bff.security_headers import SecurityHeadersMiddleware
from app.infra.db import dispose_engine
from app.infra.logging import configure_logging, get_logger


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log = get_logger("app.bff")
    log.info("bff.starting")
    try:
        yield
    finally:
        await dispose_engine()
        log.info("bff.stopped")


def create_app() -> FastAPI:
    application = FastAPI(title="Quant Platform BFF", version="0.0.0", lifespan=lifespan)
    application.add_middleware(SecurityHeadersMiddleware)
    # dagster_proxy_router MUST be registered before bff_router: the bff_router
    # contains a /{path:path} catch-all that would otherwise swallow /dagster/* routes.
    application.include_router(dagster_proxy_router)
    application.include_router(bff_router)
    return application


app = create_app()
