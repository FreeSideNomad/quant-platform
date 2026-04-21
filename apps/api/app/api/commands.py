"""Command endpoints — state-mutating actions.

This placeholder registers a single command to exercise the CQRS path
end-to-end. The full domain lives under app/domain/.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.auth_deps import AuthenticatedUser, get_current_user
from app.infra.db import session_scope
from app.infra.pgmq import send as pgmq_send

router = APIRouter()


class PingCommand(BaseModel):
    message: str = Field(min_length=1, max_length=200)


class PingResult(BaseModel):
    event_id: UUID
    enqueued_message_id: int


@router.post("/ping", response_model=PingResult)
async def ping(
    cmd: PingCommand,
    user: AuthenticatedUser = Depends(get_current_user),
) -> PingResult:
    """Append a ping event, enqueue one message to proj_ui. Single-transaction."""
    event_id = uuid4()
    payload = {"message": cmd.message, "by": user.email}
    async with session_scope() as session:
        await session.execute(
            text(
                "INSERT INTO events (id, aggregate_type, aggregate_id, event_type, payload) "
                "VALUES (:id, 'ping', :aid, 'Pinged', CAST(:p AS jsonb))"
            ),
            {
                "id": event_id,
                "aid": event_id,
                "p": PingCommand.model_validate(payload).model_dump_json(),
            },
        )
        msg_id = await pgmq_send(
            session, "proj_ui", {"event_id": str(event_id), "message": cmd.message}
        )
    return PingResult(event_id=event_id, enqueued_message_id=msg_id)
