"""FastAPI application for the `bff` role."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.bff.routes import router as bff_router
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
    application.include_router(bff_router)
    return application


app = create_app()
