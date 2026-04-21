"""Seed script — populates the local database with fixture data.

Run with: `uv run python -m app.scripts.seed`
Idempotent: safe to re-run.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from app.infra.db import dispose_engine, session_scope
from app.infra.logging import configure_logging, get_logger
from app.infra.pgmq import create_queue

log = get_logger(__name__)


async def seed() -> None:
    configure_logging()
    async with session_scope() as session:
        # Ensure the proj_ui queue exists (idempotent).
        await session.execute(
            text(
                "SELECT pgmq.create('proj_ui') WHERE NOT EXISTS "
                "(SELECT 1 FROM pgmq.list_queues() WHERE queue_name = 'proj_ui')"
            )
        )
    # Create any other queues the application expects. PGMQ raises if it exists.
    try:
        async with session_scope() as session:
            await create_queue(session, "proj_ui")
    except DatabaseError:
        pass  # already exists
    log.info("seed.done")
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(seed())
