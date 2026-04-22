"""Command endpoints — state-mutating actions.

This placeholder registers a single command to exercise the CQRS path
end-to-end. The full domain lives under app/domain/.
"""

from __future__ import annotations

import json as _json
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.auth_deps import AuthenticatedUser, get_current_user
from app.audit.log import append_audit_event
from app.dagster_defs.strategy_codegen import write_strategy_asset_file
from app.domain.strategy import StrategySpec, new_strategy_id
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


# ---------------------------------------------------------------------------
# RegisterStrategy
# ---------------------------------------------------------------------------


class RegisterStrategyRequest(BaseModel):
    family: str
    spec: dict
    actor: str


class RegisterStrategyResponse(BaseModel):
    strategy_id: str
    family: str
    created: bool


@router.post(
    "/RegisterStrategy",
    status_code=201,
    response_model=RegisterStrategyResponse,
    responses={200: {"model": RegisterStrategyResponse}},
)
async def register_strategy(req: RegisterStrategyRequest):
    """Persist a strategy spec, emit a StrategyRegistered audit event, and
    write a per-strategy Dagster asset module. Idempotent on (family, spec_hash)."""
    try:
        spec = StrategySpec.from_dict(req.spec)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid spec: {exc}")

    spec_hash = spec.spec_hash()

    async with session_scope() as session:
        existing = (
            await session.execute(
                text(
                    "SELECT id FROM strategies WHERE family = :f AND spec_hash = :h"
                ),
                {"f": req.family, "h": spec_hash},
            )
        ).scalar_one_or_none()

        if existing is not None:
            return JSONResponse(
                status_code=200,
                content={"strategy_id": existing, "family": req.family, "created": False},
            )

        strategy_id = new_strategy_id()
        await session.execute(
            text(
                """
                INSERT INTO strategies (id, family, spec, registered_by, spec_hash)
                VALUES (:id, :family, cast(:spec as jsonb), :actor, :hash)
                """
            ),
            {
                "id": strategy_id,
                "family": req.family,
                "spec": spec.canonical_json(),
                "actor": req.actor,
                "hash": spec_hash,
            },
        )
        await append_audit_event(
            session,
            actor=req.actor,
            event_type="StrategyRegistered",
            aggregate_type="Strategy",
            aggregate_id=strategy_id,
            payload={"family": req.family, "spec_hash": spec_hash},
        )
        # Drop the per-strategy Dagster asset file. Dagster's
        # code-locations mechanism reloads strategies/ on file change.
        write_strategy_asset_file(
            strategy_id=strategy_id, family=req.family, spec=spec, spec_hash=spec_hash,
        )
        await session.commit()

    return RegisterStrategyResponse(
        strategy_id=strategy_id, family=req.family, created=True
    )
