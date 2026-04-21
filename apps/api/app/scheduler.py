"""Scheduler role — APScheduler daemon emitting periodic messages."""

from __future__ import annotations

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.infra.logging import configure_logging, get_logger

log = get_logger(__name__)


async def heartbeat() -> None:
    log.info("scheduler.heartbeat")


async def main() -> None:
    configure_logging()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(heartbeat, "interval", seconds=60, id="heartbeat")
    scheduler.start()
    log.info("scheduler.started")
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
