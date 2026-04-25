"""Strategy base class — users subclass this to implement a trading strategy.

`train_and_validate(df)` does NOT invoke the promotion gate; that's M4.
In M3 it only performs walk-forward training + MLflow pyfunc packaging
+ audit-event emission.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any

import mlflow
import numpy as np
import pandas as pd
import polars as pl

from quantplatform.sdk._config import apply_mlflow_s3_env
from quantplatform.sdk.audit import emit_event
from quantplatform.sdk.run import current_run_id
from quantplatform.validation.walk_forward import WalkForwardConfig, fold_dates


def _pl_to_pd(df: pl.DataFrame) -> pd.DataFrame:
    """Polars -> pandas without pyarrow.

    Both `polars.DataFrame.to_pandas()` and `polars.from_pandas()` go
    through pyarrow when any column has a non-trivial dtype, which
    would force a ~50MB transitive dep on every quantplatform install
    just for sklearn/LightGBM feature-name preservation and for the
    MLflow signature boundary. The manual column-by-column copy below
    handles the dtypes this code path actually sees: numeric (Float64,
    Int64), Date / Datetime (cast to a numpy-compatible resolution),
    Boolean, Utf8. Per the SDK design policy: the polars↔pandas
    boundary is one helper, not a dep. If a future feature path needs
    Categorical / Decimal / Object, add pyarrow as a dep — don't grow
    this helper.
    """
    out: dict[str, np.ndarray] = {}
    for c in df.columns:
        s = df[c]
        # pl.Date converts to numpy as datetime64[D], which round-trips
        # through pandas fine but breaks `pl.Series` reconstruction on
        # the way back. Cast to ms-resolution so the round-trip survives.
        if s.dtype == pl.Date:
            out[c] = s.cast(pl.Datetime("ms")).to_numpy()
        else:
            out[c] = s.to_numpy()
    return pd.DataFrame(out)


def _pd_to_pl(df: pd.DataFrame) -> pl.DataFrame:
    """Pandas -> polars without pyarrow. Mirror of `_pl_to_pd`.

    Datetime columns at any numpy-supported resolution (`[ms]`, `[us]`,
    `[ns]`, `[D]` for datetimes only) round-trip cleanly. Non-trivial
    pandas extension dtypes (Int64, categorical) would need pyarrow —
    not used in this code path.
    """
    return pl.DataFrame({c: df[c].to_numpy() for c in df.columns})


DEFAULT_WF_CONFIG = WalkForwardConfig(
    step="month",
    train_window="3y",
    test_window="1m",
    min_folds=8,
)


class Strategy(ABC):
    """Base class for a quant strategy."""

    name: str
    thresholds: dict[str, Any] = {}

    def __init__(self) -> None:
        if not getattr(self, "name", None):
            raise TypeError(
                f"{type(self).__name__} must set a class-level `name` attribute"
            )
        self._fitted_model: Any = None

    @abstractmethod
    def features(self, df: pl.DataFrame) -> pl.DataFrame:
        """Return a DataFrame of features (including the `date` column for walk-forward)."""
        ...

    @abstractmethod
    def target(self, df: pl.DataFrame) -> pl.Series:
        """Return a Series of target values aligned with df rows."""
        ...

    @abstractmethod
    def model(self) -> Any:
        """Return an unfit sklearn-compatible regressor (fit/predict API)."""
        ...

    def train_and_validate(
        self,
        df: pl.DataFrame,
        *,
        wf_config: WalkForwardConfig = DEFAULT_WF_CONFIG,
    ) -> dict[str, Any]:
        """Walk-forward train + MLflow-log pyfunc. Returns a summary dict.

        In M3 this does NOT invoke PBO/DSR/CPCV gates — that's M4.
        """
        # Lazy import: mlflow.pyfunc pulls in pandas at import time; defer to here
        # so that importing `quantplatform` itself doesn't require pandas.
        import mlflow.pyfunc as _mlflow_pyfunc  # noqa: PLC0415

        run_id = current_run_id()

        feat_df = self.features(df)
        # Target is computed on the feature-transformed df so lengths match
        # (features() may drop rows via drop_nulls / shift).
        y = self.target(feat_df)

        # Align feat_df and y; drop rows where target is NaN
        aligned = feat_df.with_columns(_y=y)
        aligned = aligned.filter(pl.col("_y").is_not_null())

        if "date" not in aligned.columns:
            raise ValueError(
                "features(df) must preserve a `date` column for walk-forward scheduling"
            )

        data_start = aligned["date"].min()
        data_end = aligned["date"].max()
        if isinstance(data_start, datetime):
            data_start = data_start.date()
        if isinstance(data_end, datetime):
            data_end = data_end.date()

        # Enumerate folds — walk_forward.fold_dates raises ValueError if < min_folds
        folds = list(fold_dates(wf_config, data_start=data_start, data_end=data_end))

        # Feature columns = everything except `date` and `_y`
        feature_cols = [c for c in aligned.columns if c not in {"date", "_y"}]

        # Connect to MLflow + translate PQ_S3_* into the AWS_*/MLFLOW_S3
        # env vars boto3 reads. Done together because every MLflow run
        # logs an artifact at the end, which uses the S3 client; if the
        # shim runs late, log_model raises NoCredentialsError.
        mlflow.set_tracking_uri(
            os.environ.get("PQ_MLFLOW_TRACKING_URI", "http://localhost:15000")
        )
        apply_mlflow_s3_env()
        experiment_name = f"quant-platform/{self.name}"
        mlflow.set_experiment(experiment_name)

        fold_metrics: list[dict[str, float]] = []
        with mlflow.start_run(run_name=f"run-{run_id[:8]}") as mlflow_run:
            mlflow_run_id = mlflow_run.info.run_id
            mlflow.log_params({
                "strategy_name": self.name,
                "wf_step": wf_config.step,
                "wf_train_window": wf_config.train_window,
                "wf_test_window": wf_config.test_window,
                "n_folds": len(folds),
            })

            for fi, fold in enumerate(folds):
                train_slice = aligned.filter(
                    (pl.col("date") >= fold.train_start) & (pl.col("date") <= fold.train_end)
                )
                test_slice = aligned.filter(
                    (pl.col("date") >= fold.test_start) & (pl.col("date") <= fold.test_end)
                )
                if train_slice.height == 0 or test_slice.height == 0:
                    continue

                estimator = self.model()
                # Convert via pandas so sklearn/LightGBM can capture feature
                # names on fit AND see them on predict — otherwise sklearn
                # logs "X does not have valid feature names" each fold.
                X_train = _pl_to_pd(train_slice.select(feature_cols))
                y_train = train_slice["_y"].to_numpy()
                X_test = _pl_to_pd(test_slice.select(feature_cols))
                y_test = test_slice["_y"].to_numpy()

                estimator.fit(X_train, y_train)
                preds = estimator.predict(X_test)

                rmse = float(np.sqrt(np.mean((preds - y_test) ** 2)))
                fold_metrics.append({"fold": fi, "rmse": rmse})
                mlflow.log_metric(f"fold_{fi}_rmse", rmse, step=fi)

            if not fold_metrics:
                raise RuntimeError("no folds produced predictions; data too sparse?")

            mean_rmse = float(np.mean([m["rmse"] for m in fold_metrics]))
            std_rmse = float(np.std([m["rmse"] for m in fold_metrics]))
            mlflow.log_metric("mean_rmse", mean_rmse)
            mlflow.log_metric("std_rmse", std_rmse)

            # Fit final model on the full aligned dataset for pyfunc packaging
            X_full = _pl_to_pd(aligned.select(feature_cols))
            y_full = aligned["_y"].to_numpy()
            final_model = self.model()
            final_model.fit(X_full, y_full)
            self._fitted_model = final_model

            # Pack the feature computation + model as a pyfunc.
            #
            # Per the SDK design policy ("Data-frame library policy" in
            # docs/superpowers/specs/2026-04-23-quant-mvp-design.md):
            # the wrapper accepts pandas at the MLflow boundary because
            # MLflow's signature/serving layer doesn't speak polars
            # (pandas/numpy/dict/spark/scipy.sparse only). Inside the
            # wrapper we convert to polars at the user-facing boundary,
            # since user `features()` is a polars contract.
            #
            # The wrapper accepts a RAW input frame (OHLCV-shaped); it
            # applies user `features()` then `_fitted_model.predict()`.
            # The MLflow ModelSignature therefore reflects the raw input
            # shape (the dataset's schema), not the post-features feature
            # matrix shape — that's the contract serving callers see.
            _strategy = self
            _feature_cols = feature_cols

            class _PyFuncWrapper(_mlflow_pyfunc.PythonModel):
                def predict(self, context: Any, model_input: pd.DataFrame) -> np.ndarray:  # type: ignore[override]
                    batch = _pd_to_pl(model_input)
                    feats = _strategy.features(batch)
                    X = _pl_to_pd(feats.select(_feature_cols))
                    return _strategy._fitted_model.predict(X)

            # Build an explicit ModelSignature from a real raw-input slice
            # so MLflow records the wrapper's actual input/output shape.
            # Slice size = max walk-forward lookback + a few rows so
            # `features()` can compute rolling stats and drop_nulls
            # without producing an empty frame (the slice is run through
            # the wrapper once by log_model to validate the signature).
            wrapper = _PyFuncWrapper()
            input_example = _pl_to_pd(df.head(60))
            sample_output = wrapper.predict(None, input_example)
            signature = mlflow.models.infer_signature(input_example, sample_output)

            # MLflow 3.x: `artifact_path` → `name`; the returned object's
            # `.model_uri` is the canonical models:/<id> URI (the prior
            # `runs:/<run>/<path>` form is deprecated as part of "logged
            # models become first-class entities" — see MLflow 3 migration
            # guide).
            logged = _mlflow_pyfunc.log_model(
                name="model",
                python_model=wrapper,
                signature=signature,
                input_example=input_example,
            )
            mlflow_model_uri = logged.model_uri

        # Emit ModelTrained audit event
        emit_event(
            run_id=run_id,
            event_type="ModelTrained",
            payload={
                "strategy_name": self.name,
                "mlflow_run_id": mlflow_run_id,
                "mlflow_model_uri": mlflow_model_uri,
                "n_folds": len(fold_metrics),
                "mean_rmse": mean_rmse,
                "std_rmse": std_rmse,
            },
        )

        return {
            "mlflow_run_id": mlflow_run_id,
            "mlflow_model_uri": mlflow_model_uri,
            "fold_metrics": fold_metrics,
            "mean_rmse": mean_rmse,
            "std_rmse": std_rmse,
        }
