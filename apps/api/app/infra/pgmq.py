"""Thin async PGMQ client wrapper.

PGMQ is a Postgres extension that provides SQS-like queue semantics. Each
function below maps to a `pgmq.*` SQL function; the client is async because
the rest of the application is.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class PGMQMessage:
    msg_id: int
    read_ct: int
    enqueued_at: Any
    vt: Any
    message: dict[str, Any]


async def create_queue(session: AsyncSession, queue_name: str) -> None:
    await session.execute(text("SELECT pgmq.create(:q)"), {"q": queue_name})


async def send(session: AsyncSession, queue_name: str, message: dict[str, Any]) -> int:
    result = await session.execute(
        text("SELECT * FROM pgmq.send(:q, CAST(:msg AS jsonb))"),
        {"q": queue_name, "msg": json.dumps(message)},
    )
    row = result.first()
    assert row is not None
    return int(row[0])


async def read(
    session: AsyncSession,
    queue_name: str,
    visibility_timeout_seconds: int = 30,
    batch_size: int = 10,
) -> list[PGMQMessage]:
    result = await session.execute(
        text("SELECT msg_id, read_ct, enqueued_at, vt, message FROM pgmq.read(:q, :vt, :qty)"),
        {"q": queue_name, "vt": visibility_timeout_seconds, "qty": batch_size},
    )
    return [
        PGMQMessage(msg_id=row[0], read_ct=row[1], enqueued_at=row[2], vt=row[3], message=row[4])
        for row in result.fetchall()
    ]


async def delete(session: AsyncSession, queue_name: str, msg_id: int) -> bool:
    result = await session.execute(
        text("SELECT pgmq.delete(:q, :msg_id)"),
        {"q": queue_name, "msg_id": msg_id},
    )
    row = result.first()
    return bool(row[0]) if row is not None else False


async def archive(session: AsyncSession, queue_name: str, msg_id: int) -> bool:
    result = await session.execute(
        text("SELECT pgmq.archive(:q, :msg_id)"),
        {"q": queue_name, "msg_id": msg_id},
    )
    row = result.first()
    return bool(row[0]) if row is not None else False
