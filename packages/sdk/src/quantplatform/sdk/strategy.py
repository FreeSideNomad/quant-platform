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
import polars as pl

from quantplatform.sdk.audit import emit_event
from quantplatform.sdk.run import current_run_id
from quantplatform.validation.walk_forward import WalkForwardConfig, fold_dates


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

        # Connect to MLflow
        mlflow.set_tracking_uri(
            os.environ.get("PQ_MLFLOW_TRACKING_URI", "http://localhost:15000")
        )
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
                X_train = train_slice.select(feature_cols).to_pandas()
                y_train = train_slice["_y"].to_numpy()
                X_test = test_slice.select(feature_cols).to_pandas()
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
            X_full = aligned.select(feature_cols).to_pandas()
            y_full = aligned["_y"].to_numpy()
            final_model = self.model()
            final_model.fit(X_full, y_full)
            self._fitted_model = final_model

            # Pack the feature computation + model as a pyfunc.
            # The wrapper holds a reference to this Strategy instance (closure),
            # keeping features + fitted model coupled for inference.
            _strategy = self
            _feature_cols = feature_cols

            class _PyFuncWrapper(_mlflow_pyfunc.PythonModel):
                # No type hint on model_input: MLflow's schema-from-type-hint
                # inference wants `list[pl.DataFrame]` (it assumes batched
                # input). Without the hint MLflow leaves schema inference to
                # an explicit input_example, which the strategy may add later.
                def predict(self, context, model_input):  # type: ignore[override]
                    feats = _strategy.features(model_input)
                    X = feats.select(_feature_cols).to_pandas()
                    return _strategy._fitted_model.predict(X)

            _mlflow_pyfunc.log_model(
                artifact_path="model",
                python_model=_PyFuncWrapper(),
            )
            mlflow_model_uri = f"runs:/{mlflow_run_id}/model"

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
