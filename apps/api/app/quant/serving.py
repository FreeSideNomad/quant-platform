"""Inference wrapper. Loads a LightGBM booster and produces predictions.

Prod model caching: reload when the registered `Production` version changes.
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass
from datetime import date

import lightgbm as lgb
import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.infra.logging import get_logger
from app.quant.pipeline import FEATURE_COLUMNS

log = get_logger(__name__)


@dataclass
class LoadedModel:
    model_id: str
    version: str
    booster: lgb.Booster


_cache: dict[str, LoadedModel] = {}
_lock = threading.Lock()


def load_production_model(model_name: str) -> LoadedModel:
    """Fetch the current production-stage version from MLflow and cache it."""
    import mlflow

    mlflow.set_tracking_uri(get_settings().mlflow_tracking_uri)
    client = mlflow.MlflowClient()

    # Prefer alias=production; fall back to latest model version
    try:
        mv = client.get_model_version_by_alias(model_name, "production")
    except Exception as exc:
        versions = client.search_model_versions(f"name = '{model_name}'")
        if not versions:
            raise RuntimeError(f"no model registered under {model_name!r}") from exc
        mv = sorted(versions, key=lambda v: int(v.version))[-1]

    with _lock:
        cached = _cache.get(model_name)
        if cached and cached.version == mv.version:
            return cached

        from mlflow import artifacts as mlflow_artifacts

        local_path = mlflow_artifacts.download_artifacts(mv.source)
        import os

        if os.path.isdir(local_path):
            candidate = os.path.join(local_path, "model.lgb")
            if not os.path.exists(candidate):
                candidate = os.path.join(local_path, "model.txt")
            local_path = candidate
        booster = lgb.Booster(model_file=local_path)
        loaded = LoadedModel(model_id=model_name, version=mv.version, booster=booster)
        _cache[model_name] = loaded
        return loaded


async def latest_features_for(
    session: AsyncSession, instrument: str, as_of: date
) -> dict[str, float] | None:
    row = await session.execute(
        text(
            """
            SELECT mom_5, mom_20, vol_20, return_mean_20, hl_range, vol_ratio_20
            FROM features_gold
            WHERE instrument = :i
              AND trade_date <= :d
              AND knowable_at <= CAST(:d AS timestamptz) + interval '23:59:59'
            ORDER BY trade_date DESC
            LIMIT 1
            """
        ),
        {"i": instrument, "d": as_of},
    )
    r = row.first()
    if r is None:
        return None
    names = ("mom_5", "mom_20", "vol_20", "return_mean_20", "hl_range", "vol_ratio_20")
    return {n: float(v) for n, v in zip(names, r, strict=True) if v is not None}


@dataclass
class PredictionResult:
    prediction: float
    model_version: str
    feature_hash: str
    latency_ms: int


def predict(model_name: str, features: dict[str, float]) -> PredictionResult:
    start = time.perf_counter()
    model = load_production_model(model_name)
    vec = np.array([[features[c] for c in FEATURE_COLUMNS]], dtype=np.float64)
    pred_raw = np.asarray(model.booster.predict(vec), dtype=np.float64)
    pred = float(pred_raw[0])
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    feature_hash = hashlib.sha256(
        ",".join(f"{features[c]:.10g}" for c in FEATURE_COLUMNS).encode()
    ).hexdigest()[:16]
    return PredictionResult(
        prediction=pred,
        model_version=model.version,
        feature_hash=feature_hash,
        latency_ms=elapsed_ms,
    )


async def log_inference(
    session: AsyncSession,
    *,
    model_id: str,
    model_version: str,
    instrument: str,
    as_of: date,
    feature_hash: str,
    prediction: float,
    latency_ms: int,
    requested_by: str | None,
) -> str:
    import uuid

    inference_id = str(uuid.uuid4())
    await session.execute(
        text(
            """
            INSERT INTO inference_log(
              id, model_id, model_version, instrument, as_of_date,
              feature_hash, prediction, latency_ms, requested_by
            ) VALUES (:id, :mid, :mv, :inst, :dt, :fh, :p, :ms, :by)
            """
        ),
        {
            "id": inference_id,
            "mid": model_id,
            "mv": model_version,
            "inst": instrument,
            "dt": as_of,
            "fh": feature_hash,
            "p": prediction,
            "ms": latency_ms,
            "by": requested_by,
        },
    )
    return inference_id


def invalidate_cache(model_name: str | None = None) -> None:
    """Call after promoting a new model version."""
    with _lock:
        if model_name is None:
            _cache.clear()
        else:
            _cache.pop(model_name, None)


__all__ = [
    "LoadedModel",
    "PredictionResult",
    "invalidate_cache",
    "latest_features_for",
    "load_production_model",
    "log_inference",
    "predict",
]
