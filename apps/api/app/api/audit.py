"""Audit lineage drill-down — the LP-facing 60-second query."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.infra.db import session_scope


router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/inference/{inference_id}/lineage")
async def lineage_for_inference(inference_id: str):
    async with session_scope() as session:
        inf = (
            await session.execute(
                text(
                    """SELECT id, model_id, model_version, instrument,
                              as_of_date, prediction, latency_ms, requested_at
                       FROM inference_log WHERE id = :id"""
                ),
                {"id": inference_id},
            )
        ).one_or_none()
        if inf is None:
            raise HTTPException(status_code=404, detail="inference not found")

        mv = (
            await session.execute(
                text(
                    """SELECT model_id, version, stage, training_run_id,
                              mlflow_model_version, pbo, dsr_probability,
                              walk_forward_fold_count
                       FROM model_versions WHERE model_id = :m AND version = :v"""
                ),
                {"m": inf.model_id, "v": inf.model_version},
            )
        ).one_or_none()

        tr = None
        if mv and mv.training_run_id:
            tr = (
                await session.execute(
                    text(
                        """SELECT id, model_id, status, started_at, completed_at
                           FROM training_runs WHERE id = :id"""
                    ),
                    {"id": mv.training_run_id},
                )
            ).one_or_none()

        events = (
            await session.execute(
                text(
                    """SELECT id, occurred_at, actor, event_type, aggregate_type,
                              aggregate_id, payload
                       FROM audit_log
                       WHERE aggregate_type = 'ModelVersion'
                         AND aggregate_id = :av
                       ORDER BY id ASC"""
                ),
                {"av": f"{inf.model_id}/{inf.model_version}"},
            )
        ).all()

    return {
        "inference": {
            "id": inf.id,
            "model_id": inf.model_id,
            "model_version": inf.model_version,
            "instrument": inf.instrument,
            "requested_at": inf.requested_at.isoformat() if inf.requested_at else None,
            "latency_ms": inf.latency_ms,
        },
        "model_version": (
            {
                "model_id": mv.model_id,
                "version": mv.version,
                "stage": mv.stage,
                "training_run_id": mv.training_run_id,
                "mlflow_model_version": mv.mlflow_model_version,
                "pbo": mv.pbo,
                "dsr_probability": mv.dsr_probability,
                "walk_forward_fold_count": mv.walk_forward_fold_count,
            }
            if mv
            else None
        ),
        "training_run": (
            {
                "id": tr.id,
                "model_id": tr.model_id,
                "status": tr.status,
                "started_at": tr.started_at.isoformat() if tr.started_at else None,
                "completed_at": tr.completed_at.isoformat() if tr.completed_at else None,
            }
            if tr
            else None
        ),
        "audit_events": [
            {
                "id": e.id,
                "occurred_at": e.occurred_at.isoformat(),
                "actor": e.actor,
                "event_type": e.event_type,
                "payload": e.payload,
            }
            for e in events
        ],
    }
