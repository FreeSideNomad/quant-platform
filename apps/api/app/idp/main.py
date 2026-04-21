"""FastAPI application for the `idp` role."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.idp.routes import router as idp_router
from app.infra.db import dispose_engine
from app.infra.logging import configure_logging, get_logger


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log = get_logger("app.idp")
    log.info("idp.starting")
    try:
        yield
    finally:
        await dispose_engine()
        log.info("idp.stopped")


def create_app() -> FastAPI:
    application = FastAPI(title="Quant Platform IdP", version="0.0.0", lifespan=lifespan)
    application.include_router(idp_router)
    return application


app = create_app()
