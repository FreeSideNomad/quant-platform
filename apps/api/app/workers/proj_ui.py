"""proj_ui worker — projects Pinged events into the proj_ui_pings read table.

Idempotent: primary key on event_id prevents double-insert.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.infra.db import session_scope
from app.infra.logging import configure_logging, get_logger
from app.infra.pgmq import PGMQMessage
from app.workers.base import Worker

log = get_logger(__name__)


class ProjUIWorker(Worker):
    queue_name = "proj_ui"
    concurrency = 4

    async def handle(self, message: PGMQMessage) -> None:
        event_id = message.message.get("event_id")
        text_message = message.message.get("message", "")
        if not event_id:
            log.warning("proj_ui.missing_event_id", payload=message.message)
            return
        async with session_scope() as session:
            await session.execute(
                text(
                    "INSERT INTO proj_ui_pings (event_id, message, projected_at) "
                    "VALUES (:id, :msg, now()) ON CONFLICT (event_id) DO NOTHING"
                ),
                {"id": event_id, "msg": text_message},
            )


async def main() -> None:
    configure_logging()
    await ProjUIWorker().run()


if __name__ == "__main__":
    asyncio.run(main())
