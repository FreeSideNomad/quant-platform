"""LightGBM training on the gold feature set with MLflow tracking and registry.

Shape:
  1. Read gold features where `knowable_at <= as_of` and a forward target exists
  2. Time-ordered train/validation split
  3. Fit LightGBM regressor on the 6-feature set
  4. Log params, metrics, artefact to MLflow, register as model version
  5. Update the `training_runs` and `model_versions` tables
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import polars as pl
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.infra.logging import get_logger
from app.quant.pipeline import FEATURE_COLUMNS

log = get_logger(__name__)

DEFAULT_PARAMS: dict[str, Any] = {
    "objective": "regression",
    "metric": "l2",
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_data_in_leaf": 20,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.9,
    "bagging_freq": 5,
    "verbose": -1,
}


@dataclass
class TrainingArtefact:
    mlflow_run_id: str
    metrics: dict[str, float]
    model_path: str
    dataset_hash: str


async def load_training_data(
    session: AsyncSession,
    *,
    as_of: date,
    train_start: date,
    train_end: date,
    instruments: list[str] | None,
) -> pl.DataFrame:
    universe_clause = ""
    params: dict[str, Any] = {
        "as_of": as_of,
        "start": train_start,
        "end": train_end,
    }
    if instruments:
        universe_clause = "AND instrument = ANY(:universe)"
        params["universe"] = instruments

    result = await session.execute(
        text(
            f"""
            SELECT instrument, trade_date,
                   mom_5, mom_20, vol_20, return_mean_20, hl_range, vol_ratio_20,
                   target_fwd_1d
            FROM features_gold
            WHERE knowable_at <= CAST(:as_of AS timestamptz) + interval '23:59:59'
              AND trade_date BETWEEN :start AND :end
              AND target_fwd_1d IS NOT NULL
              {universe_clause}
            ORDER BY trade_date, instrument
            """
        ),
        params,
    )
    rows = result.fetchall()
    if not rows:
        raise RuntimeError("no training data available in the requested window")
    cols = [
        "instrument",
        "trade_date",
        "mom_5",
        "mom_20",
        "vol_20",
        "return_mean_20",
        "hl_range",
        "vol_ratio_20",
        "target_fwd_1d",
    ]
    return pl.DataFrame({c: [r[i] for r in rows] for i, c in enumerate(cols)})


def _dataset_hash(df: pl.DataFrame) -> str:
    # Deterministic hash of sorted row tuples — used as reproducibility proof.
    payload = df.sort(["instrument", "trade_date"]).to_pandas().to_csv(index=False).encode()
    return hashlib.sha256(payload).hexdigest()


def _split_by_date(df: pl.DataFrame, val_frac: float = 0.2) -> tuple[pl.DataFrame, pl.DataFrame]:
    dates = sorted(df["trade_date"].unique().to_list())
    cutoff_idx = max(int(len(dates) * (1 - val_frac)), 1)
    cutoff = dates[cutoff_idx - 1]
    train = df.filter(pl.col("trade_date") <= cutoff)
    val = df.filter(pl.col("trade_date") > cutoff)
    return train, val


def train_lgbm(
    df: pl.DataFrame,
    *,
    params: dict[str, Any] | None = None,
    num_boost_round: int = 200,
    artefact_dir: Path | None = None,
    log_to_mlflow: bool = True,
) -> TrainingArtefact:
    import mlflow

    merged_params = {**DEFAULT_PARAMS, **(params or {})}

    train_df, val_df = _split_by_date(df, val_frac=0.2)
    feature_cols = list(FEATURE_COLUMNS)

    x_train = train_df.select(feature_cols).to_numpy()
    y_train = train_df["target_fwd_1d"].to_numpy()
    x_val = val_df.select(feature_cols).to_numpy()
    y_val = val_df["target_fwd_1d"].to_numpy()

    dataset_hash = _dataset_hash(df)

    # Persist model to disk (always needed, even when not logging to MLflow)
    directory = artefact_dir or Path(tempfile.mkdtemp(prefix="qp-model-"))
    model_path = directory / "model.txt"

    def _do_train(run_id: str) -> TrainingArtefact:
        dtrain = lgb.Dataset(x_train, label=y_train)
        dval = lgb.Dataset(x_val, label=y_val, reference=dtrain)
        booster = lgb.train(
            merged_params,
            dtrain,
            num_boost_round=num_boost_round,
            valid_sets=[dtrain, dval],
            valid_names=["train", "val"],
            callbacks=[lgb.early_stopping(25), lgb.log_evaluation(0)],
        )

        train_pred = np.asarray(
            booster.predict(x_train, num_iteration=booster.best_iteration), dtype=np.float64
        )
        val_pred = np.asarray(
            booster.predict(x_val, num_iteration=booster.best_iteration), dtype=np.float64
        )
        m = {
            "train_rmse": float(np.sqrt(np.mean((train_pred - y_train) ** 2))),
            "val_rmse": float(np.sqrt(np.mean((val_pred - y_val) ** 2))),
            "val_ic": (
                float(np.corrcoef(val_pred, y_val)[0, 1])
                if len(y_val) > 2 and np.std(val_pred) > 1e-12 and np.std(y_val) > 1e-12
                else float("nan")
            ),
        }
        booster.save_model(str(model_path))
        return TrainingArtefact(
            mlflow_run_id=run_id,
            metrics=m,
            model_path=str(model_path),
            dataset_hash=dataset_hash,
        )

    if log_to_mlflow:
        mlflow.set_tracking_uri(get_settings().mlflow_tracking_uri)
        mlflow.set_experiment("qlib-lgbm")
        with mlflow.start_run() as run:
            mlflow.log_params(merged_params)
            mlflow.log_param("num_boost_round", num_boost_round)
            mlflow.log_param("dataset_hash", dataset_hash)
            mlflow.log_param("train_rows", len(y_train))
            mlflow.log_param("val_rows", len(y_val))

            artefact = _do_train(run.info.run_id)

            mlflow.log_metrics({k: v for k, v in artefact.metrics.items() if not np.isnan(v)})
            mlflow.log_artifact(str(model_path))
            mlflow.log_dict(
                {"feature_columns": feature_cols, "params": merged_params}, "feature_spec.json"
            )
            return artefact
    else:
        return _do_train(run_id="")


def register_model_version(
    *,
    model_name: str,
    model_path: str,
    mlflow_run_id: str,
) -> str | None:
    """Register the trained booster with MLflow's Model Registry. Returns version string."""
    import mlflow
    from mlflow.lightgbm import log_model

    mlflow.set_tracking_uri(get_settings().mlflow_tracking_uri)

    booster = lgb.Booster(model_file=model_path)

    with mlflow.start_run(run_id=mlflow_run_id):
        model_info = log_model(
            booster,
            name="model",
            registered_model_name=model_name,
        )
    return getattr(model_info, "registered_model_version", None)


def export_summary(artefact: TrainingArtefact) -> dict[str, Any]:
    return {
        "mlflow_run_id": artefact.mlflow_run_id,
        "metrics": artefact.metrics,
        "dataset_hash": artefact.dataset_hash,
    }


__all__ = [
    "DEFAULT_PARAMS",
    "FoldResult",
    "TrainingArtefact",
    "WalkForwardArtefact",
    "_compute_ic",
    "_compute_sharpe",
    "export_summary",
    "load_training_data",
    "register_model_version",
    "train_lgbm",
    "train_lgbm_walk_forward",
]


# Helper for worker/handler to serialise JSON-safely
def safe_jsonify(obj: Any) -> str:
    return json.dumps(obj, default=str)


# ---------------------------------------------------------------------------
# Walk-forward training
# ---------------------------------------------------------------------------

from scipy.stats import spearmanr as _spearmanr

from app.infra.db import session_scope as _session_scope  # noqa: E402
from app.quant.walk_forward import WalkForwardConfig, fold_dates  # noqa: E402


@dataclass(frozen=True)
class FoldResult:
    index: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    in_sample_ic: float | None
    out_of_sample_ic: float
    out_of_sample_sharpe: float


@dataclass(frozen=True)
class WalkForwardArtefact:
    training_run_id: str
    fold_count: int
    folds: list[FoldResult]
    aggregate_oos_ic: float
    aggregate_oos_sharpe: float


def _compute_ic(predictions: np.ndarray, actuals: np.ndarray) -> float:
    """Spearman rank correlation between predictions and actuals."""
    if len(predictions) < 3:
        return 0.0
    rho, _ = _spearmanr(predictions, actuals)
    return float(rho) if not np.isnan(rho) else 0.0


def _compute_sharpe(returns: np.ndarray, periods_per_year: int = 252) -> float:
    if len(returns) < 2 or returns.std(ddof=1) == 0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(periods_per_year))


async def train_lgbm_walk_forward(
    *,
    training_run_id: str,
    wf_config: WalkForwardConfig,
    as_of: date,
    params: dict[str, Any] | None = None,
    instruments: list[str] | None = None,
) -> WalkForwardArtefact:
    """Walk-forward train + evaluate; persist per-fold metrics to walk_forward_folds."""
    # Determine the date bounds of available gold features.
    async with _session_scope() as session:
        bounds_row = (
            await session.execute(
                text("SELECT min(trade_date), max(trade_date) FROM features_gold")
            )
        ).one()

    data_start, data_end_raw = bounds_row[0], bounds_row[1]
    if data_start is None or data_end_raw is None:
        raise RuntimeError(
            "features_gold is empty — seed data before calling train_lgbm_walk_forward"
        )
    data_end = min(data_end_raw, as_of)

    folds_list = list(fold_dates(wf_config, data_start=data_start, data_end=data_end))

    fold_results: list[FoldResult] = []
    feature_cols = list(FEATURE_COLUMNS)

    for fold in folds_list:
        # Load train and test data inside their own sessions.
        async with _session_scope() as session:
            train_df = await load_training_data(
                session,
                as_of=as_of,
                train_start=fold.train_start,
                train_end=fold.train_end,
                instruments=instruments,
            )
        async with _session_scope() as session:
            test_df = await load_training_data(
                session,
                as_of=as_of,
                train_start=fold.test_start,
                train_end=fold.test_end,
                instruments=instruments,
            )

        # Combine train+test into one df so train_lgbm can do its own split,
        # then train with log_to_mlflow=False (per-fold runs not tracked in MLflow).
        artefact = train_lgbm(
            train_df,
            params=params,
            log_to_mlflow=False,
        )

        # Load the saved booster to generate OOS predictions on test_df.
        booster = lgb.Booster(model_file=artefact.model_path)
        x_test = test_df.select(feature_cols).to_numpy()
        oos_predictions = np.asarray(
            booster.predict(x_test, num_iteration=booster.best_iteration), dtype=np.float64
        )
        oos_actuals = test_df["target_fwd_1d"].to_numpy()

        oos_ic = _compute_ic(oos_predictions, oos_actuals)

        # Simple long/short signal: top half vs. bottom half by prediction.
        positions = np.where(oos_predictions >= np.median(oos_predictions), 1.0, -1.0)
        oos_returns = positions * oos_actuals
        oos_sharpe = _compute_sharpe(oos_returns)

        fold_results.append(
            FoldResult(
                index=fold.index,
                train_start=fold.train_start,
                train_end=fold.train_end,
                test_start=fold.test_start,
                test_end=fold.test_end,
                in_sample_ic=None,
                out_of_sample_ic=oos_ic,
                out_of_sample_sharpe=oos_sharpe,
            )
        )

    # Persist per-fold metrics to the database.
    async with _session_scope() as session:
        for f in fold_results:
            await session.execute(
                text(
                    """
                    INSERT INTO walk_forward_folds
                        (training_run_id, fold_index, train_start, train_end,
                         test_start, test_end, in_sample_ic, out_of_sample_ic,
                         out_of_sample_sharpe, metrics)
                    VALUES
                        (:rid, :idx, :ts, :te, :tts, :tte, :is_ic, :oos_ic,
                         :oos_sharpe, '{}'::jsonb)
                    ON CONFLICT (training_run_id, fold_index) DO UPDATE SET
                        out_of_sample_ic = EXCLUDED.out_of_sample_ic,
                        out_of_sample_sharpe = EXCLUDED.out_of_sample_sharpe
                    """
                ),
                {
                    "rid": training_run_id,
                    "idx": f.index,
                    "ts": f.train_start,
                    "te": f.train_end,
                    "tts": f.test_start,
                    "tte": f.test_end,
                    "is_ic": f.in_sample_ic,
                    "oos_ic": f.out_of_sample_ic,
                    "oos_sharpe": f.out_of_sample_sharpe,
                },
            )
        await session.commit()

    aggregate_ic = float(np.mean([f.out_of_sample_ic for f in fold_results]))
    aggregate_sharpe = float(np.mean([f.out_of_sample_sharpe for f in fold_results]))

    return WalkForwardArtefact(
        training_run_id=training_run_id,
        fold_count=len(fold_results),
        folds=fold_results,
        aggregate_oos_ic=aggregate_ic,
        aggregate_oos_sharpe=aggregate_sharpe,
    )
