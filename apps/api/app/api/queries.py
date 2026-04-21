"""Query endpoints — read from projections."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.infra.db import session_scope

router = APIRouter()


class PingRow(BaseModel):
    event_id: str
    message: str
    projected_at: datetime


@router.get("/pings", response_model=list[PingRow])
async def list_pings(limit: int = 50) -> list[PingRow]:
    async with session_scope() as session:
        result = await session.execute(
            text(
                "SELECT event_id, message, projected_at FROM proj_ui_pings "
                "ORDER BY projected_at DESC LIMIT :limit"
            ),
            {"limit": limit},
        )
        return [
            PingRow(event_id=str(row[0]), message=row[1], projected_at=row[2])
            for row in result.fetchall()
        ]
