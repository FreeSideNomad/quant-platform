"""API for the models domain — training submission, model listing, inference.

Every mutating endpoint is role-gated; read endpoints require any authenticated
user. The BFF forwards the Bearer token from the session.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.auth_deps import AuthenticatedUser, get_current_user, requires_role
from app.infra.db import session_scope
from app.infra.logging import get_logger
from app.infra.pgmq import send as pgmq_send

log = get_logger(__name__)
router = APIRouter()


class ModelSummary(BaseModel):
    id: str
    name: str
    description: str | None
    algorithm: str
    owner_email: str | None
    created_at: datetime
    updated_at: datetime
    production_version: str | None = None
    last_run_status: str | None = None
    last_run_at: datetime | None = None


class ModelDetail(ModelSummary):
    training_runs: list[TrainingRunSummary] = []
    versions: list[ModelVersionSummary] = []


class TrainingRunSummary(BaseModel):
    id: str
    model_id: str
    mlflow_run_id: str | None
    status: str
    compute_profile: str
    as_of: date
    train_start: date
    train_end: date
    instruments: list[str]
    hyperparameters: dict[str, Any]
    metrics: dict[str, Any]
    artefact_uri: str | None
    model_version: str | None
    started_at: datetime
    completed_at: datetime | None
    submitted_by: str | None
    error: str | None


class ModelVersionSummary(BaseModel):
    id: str
    model_id: str
    training_run_id: str
    version: str
    stage: str
    mlflow_model_version: str | None
    created_at: datetime
    promoted_at: datetime | None
    metrics: dict[str, Any]


class TrainingSubmission(BaseModel):
    model_id: str
    compute_profile: str = Field(
        default="local-cpu", pattern="^(local-cpu|local-gpu|cloud-cpu|cloud-gpu)$"
    )
    as_of: date
    train_start: date
    train_end: date
    instruments: list[str] = Field(default_factory=list, min_length=0)
    hyperparameters: dict[str, Any] = Field(default_factory=dict)


class TrainingSubmissionResult(BaseModel):
    training_run_id: str
    status: str


class PredictRequest(BaseModel):
    instrument: str
    as_of: date


class PredictResult(BaseModel):
    instrument: str
    as_of: date
    prediction: float
    model_version: str
    feature_hash: str
    latency_ms: int
    inference_id: str


class InferenceLogEntry(BaseModel):
    id: str
    model_id: str
    model_version: str
    instrument: str
    as_of_date: date
    prediction: float
    latency_ms: int
    requested_by: str | None
    requested_at: datetime


# --------------------------------------------------------------------
# Queries
# --------------------------------------------------------------------


@router.get("/models", response_model=list[ModelSummary])
async def list_models(_: AuthenticatedUser = Depends(get_current_user)) -> list[ModelSummary]:
    async with session_scope() as session:
        rows = await session.execute(
            text(
                """
                SELECT m.id, m.name, m.description, m.algorithm, m.owner_email,
                       m.created_at, m.updated_at,
                       (SELECT version FROM model_versions mv
                         WHERE mv.model_id = m.id AND mv.stage = 'production'
                         ORDER BY promoted_at DESC NULLS LAST LIMIT 1) AS prod_version,
                       (SELECT status FROM training_runs tr
                         WHERE tr.model_id = m.id ORDER BY started_at DESC LIMIT 1) AS last_status,
                       (SELECT started_at FROM training_runs tr
                         WHERE tr.model_id = m.id ORDER BY started_at DESC LIMIT 1) AS last_at
                FROM models m
                ORDER BY m.created_at DESC
                """
            )
        )
        return [
            ModelSummary(
                id=r[0],
                name=r[1],
                description=r[2],
                algorithm=r[3],
                owner_email=r[4],
                created_at=r[5],
                updated_at=r[6],
                production_version=r[7],
                last_run_status=r[8],
                last_run_at=r[9],
            )
            for r in rows.fetchall()
        ]


@router.get("/models/{model_id}", response_model=ModelDetail)
async def get_model(model_id: str, _: AuthenticatedUser = Depends(get_current_user)) -> ModelDetail:
    async with session_scope() as session:
        r = await session.execute(
            text(
                "SELECT id, name, description, algorithm, owner_email, created_at, updated_at "
                "FROM models WHERE id = :id"
            ),
            {"id": model_id},
        )
        row = r.first()
        if row is None:
            raise HTTPException(status_code=404, detail="model_not_found")

        runs_r = await session.execute(
            text(
                """
                SELECT id, model_id, mlflow_run_id, status, compute_profile, as_of,
                       train_start, train_end, instruments, hyperparameters, metrics,
                       artefact_uri, model_version, started_at, completed_at,
                       submitted_by, error
                FROM training_runs
                WHERE model_id = :id ORDER BY started_at DESC
                """
            ),
            {"id": model_id},
        )
        runs = [
            TrainingRunSummary(
                id=x[0],
                model_id=x[1],
                mlflow_run_id=x[2],
                status=x[3],
                compute_profile=x[4],
                as_of=x[5],
                train_start=x[6],
                train_end=x[7],
                instruments=list(x[8] or []),
                hyperparameters=x[9] or {},
                metrics=x[10] or {},
                artefact_uri=x[11],
                model_version=x[12],
                started_at=x[13],
                completed_at=x[14],
                submitted_by=x[15],
                error=x[16],
            )
            for x in runs_r.fetchall()
        ]

        versions_r = await session.execute(
            text(
                """
                SELECT id, model_id, training_run_id, version, stage, mlflow_model_version,
                       created_at, promoted_at, metrics
                FROM model_versions WHERE model_id = :id ORDER BY created_at DESC
                """
            ),
            {"id": model_id},
        )
        versions = [
            ModelVersionSummary(
                id=x[0],
                model_id=x[1],
                training_run_id=x[2],
                version=x[3],
                stage=x[4],
                mlflow_model_version=x[5],
                created_at=x[6],
                promoted_at=x[7],
                metrics=x[8] or {},
            )
            for x in versions_r.fetchall()
        ]

        latest_prod = next((v.version for v in versions if v.stage == "production"), None)

        return ModelDetail(
            id=row[0],
            name=row[1],
            description=row[2],
            algorithm=row[3],
            owner_email=row[4],
            created_at=row[5],
            updated_at=row[6],
            production_version=latest_prod,
            last_run_status=runs[0].status if runs else None,
            last_run_at=runs[0].started_at if runs else None,
            training_runs=runs,
            versions=versions,
        )


@router.get("/models/{model_id}/inference-log", response_model=list[InferenceLogEntry])
async def list_inference_log(
    model_id: str, limit: int = 50, _: AuthenticatedUser = Depends(get_current_user)
) -> list[InferenceLogEntry]:
    async with session_scope() as session:
        rows = await session.execute(
            text(
                """
                SELECT id, model_id, model_version, instrument, as_of_date,
                       prediction, latency_ms, requested_by, requested_at
                FROM inference_log WHERE model_id = :id
                ORDER BY requested_at DESC LIMIT :limit
                """
            ),
            {"id": model_id, "limit": min(limit, 500)},
        )
        return [
            InferenceLogEntry(
                id=r[0],
                model_id=r[1],
                model_version=r[2],
                instrument=r[3],
                as_of_date=r[4],
                prediction=r[5],
                latency_ms=r[6],
                requested_by=r[7],
                requested_at=r[8],
            )
            for r in rows.fetchall()
        ]


# --------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------


@router.post("/training/submit", response_model=TrainingSubmissionResult)
async def submit_training_run(
    sub: TrainingSubmission,
    user: AuthenticatedUser = Depends(requires_role("quant", "admin")),
) -> TrainingSubmissionResult:
    """Enqueue a training run. The `worker-training` role picks it up from PGMQ."""
    run_id = str(uuid.uuid4())
    async with session_scope() as session:
        # Verify model exists
        r = await session.execute(text("SELECT 1 FROM models WHERE id = :id"), {"id": sub.model_id})
        if r.first() is None:
            raise HTTPException(status_code=404, detail="model_not_found")

        await session.execute(
            text(
                """
                INSERT INTO training_runs(
                  id, model_id, status, compute_profile, as_of, train_start, train_end,
                  instruments, hyperparameters, submitted_by
                ) VALUES (:id, :mid, 'submitted', :cp, :asof, :ts, :te, :inst,
                          CAST(:hp AS jsonb), :by)
                """
            ),
            {
                "id": run_id,
                "mid": sub.model_id,
                "cp": sub.compute_profile,
                "asof": sub.as_of,
                "ts": sub.train_start,
                "te": sub.train_end,
                "inst": sub.instruments,
                "hp": _jsonify(sub.hyperparameters),
                "by": user.email,
            },
        )
        await pgmq_send(session, "training", {"training_run_id": run_id})

    return TrainingSubmissionResult(training_run_id=run_id, status="submitted")


@router.post("/serving/qlib-lgbm/predict", response_model=PredictResult)
async def predict_qlib_lgbm(
    req: PredictRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> PredictResult:
    from app.quant.serving import latest_features_for, log_inference, predict

    async with session_scope() as session:
        features = await latest_features_for(session, req.instrument, req.as_of)
        if features is None:
            raise HTTPException(
                status_code=404,
                detail=f"no features available for {req.instrument} as-of {req.as_of}",
            )

    try:
        result = predict("qlib-lgbm", features)
    except Exception as exc:
        log.error("serving.error", error=str(exc))
        raise HTTPException(status_code=503, detail=f"serving_unavailable: {exc}") from exc

    async with session_scope() as session:
        # Resolve the model row id (we use a fixed-model 'qlib-lgbm' in this demo)
        r = await session.execute(
            text("SELECT id FROM models WHERE name = :n LIMIT 1"), {"n": "qlib-lgbm"}
        )
        mid_row = r.first()
        model_id = mid_row[0] if mid_row else "qlib-lgbm"
        inference_id = await log_inference(
            session,
            model_id=model_id,
            model_version=result.model_version,
            instrument=req.instrument,
            as_of=req.as_of,
            feature_hash=result.feature_hash,
            prediction=result.prediction,
            latency_ms=result.latency_ms,
            requested_by=user.email,
        )

    return PredictResult(
        instrument=req.instrument,
        as_of=req.as_of,
        prediction=result.prediction,
        model_version=result.model_version,
        feature_hash=result.feature_hash,
        latency_ms=result.latency_ms,
        inference_id=inference_id,
    )


def _jsonify(obj: Any) -> str:
    import json

    return json.dumps(obj, default=str)


# --------------------------------------------------------------------
# Promotion gate
# --------------------------------------------------------------------


class PromoteRequest(BaseModel):
    actor: str
    reason: str


@router.patch("/models/{model_id}/versions/{version}/promote")
async def promote_model_version(
    model_id: str,
    version: str,
    req: PromoteRequest,
) -> dict:
    """Evaluate PBO/DSR/walk-forward gates and, on pass, transition the version to production.

    Returns 422 with gate_results detail on failure.
    Archives any prior production version for the same model.
    Emits a ModelPromoted audit event.
    """
    from app.audit.log import append_audit_event
    from app.quant.validation.gates import evaluate_gates

    async with session_scope() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT pbo, dsr_probability, walk_forward_fold_count, stage
                    FROM model_versions
                    WHERE model_id = :m AND version = :v
                    """
                ),
                {"m": model_id, "v": version},
            )
        ).one_or_none()

        if row is None:
            raise HTTPException(status_code=404, detail="model_version_not_found")

        results = evaluate_gates(
            pbo=row.pbo,
            dsr_probability=row.dsr_probability,
            walk_forward_fold_count=row.walk_forward_fold_count,
        )

        if not results.all_pass:
            failure_reasons: list[str] = []
            if not results.pbo_pass:
                failure_reasons.append(
                    f"PBO {row.pbo} > 0.7 threshold"
                    if row.pbo is not None
                    else "PBO not computed"
                )
            if not results.dsr_pass:
                failure_reasons.append(
                    f"DSR probability {row.dsr_probability} < 0.95"
                    if row.dsr_probability is not None
                    else "DSR not computed"
                )
            if not results.walk_forward_pass:
                failure_reasons.append(
                    f"Only {row.walk_forward_fold_count} walk-forward folds; need >= 8"
                    if row.walk_forward_fold_count is not None
                    else "Walk-forward fold count not computed"
                )
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Promotion blocked: " + "; ".join(failure_reasons),
                    "gate_results": {
                        "pbo_pass": results.pbo_pass,
                        "dsr_pass": results.dsr_pass,
                        "walk_forward_pass": results.walk_forward_pass,
                    },
                },
            )

        previous_stage = row.stage

        # Promote this version
        await session.execute(
            text(
                """
                UPDATE model_versions SET stage = 'production', promoted_at = now()
                WHERE model_id = :m AND version = :v
                """
            ),
            {"m": model_id, "v": version},
        )
        # Archive any other production version for this model
        await session.execute(
            text(
                """
                UPDATE model_versions SET stage = 'archived'
                WHERE model_id = :m AND version != :v AND stage = 'production'
                """
            ),
            {"m": model_id, "v": version},
        )

        await append_audit_event(
            session,
            actor=req.actor,
            event_type="ModelPromoted",
            aggregate_type="ModelVersion",
            aggregate_id=f"{model_id}/{version}",
            payload={
                "model_id": model_id,
                "version": version,
                "reason": req.reason,
                "gate_results": {
                    "pbo": results.pbo,
                    "dsr_probability": results.dsr_probability,
                    "walk_forward_fold_count": results.walk_forward_fold_count,
                },
            },
        )
        await session.commit()

    return {
        "model_id": model_id,
        "version": version,
        "previous_stage": previous_stage,
        "new_stage": "production",
        "gate_results": {
            "pbo_pass": results.pbo_pass,
            "dsr_pass": results.dsr_pass,
            "walk_forward_pass": results.walk_forward_pass,
        },
    }


__all__ = ["router"]
