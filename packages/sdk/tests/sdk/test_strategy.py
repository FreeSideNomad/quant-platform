"""Unit tests for Strategy base class + train_and_validate."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import numpy as np
import polars as pl
import psycopg2
import psycopg2.extras
import pytest
from sklearn.linear_model import LinearRegression

from quantplatform import Strategy, run


class _TrivialStrategy(Strategy):
    name = "trivial"

    def features(self, df: pl.DataFrame) -> pl.DataFrame:
        # Add a simple lag feature; keep `date` for walk-forward
        return df.with_columns([
            pl.col("close").shift(1).alias("lag_close"),
        ]).drop_nulls()

    def target(self, df: pl.DataFrame) -> pl.Series:
        # Next-day return
        return df["close"].pct_change().shift(-1)

    def model(self) -> LinearRegression:
        return LinearRegression()


def _synthetic_df(n_days: int = 1500) -> pl.DataFrame:
    rng = np.random.default_rng(seed=42)
    dates = [date(2018, 1, 1) + timedelta(days=i) for i in range(n_days)]
    close = 100 + np.cumsum(rng.normal(0.05, 1.0, n_days))
    return pl.DataFrame({
        "date": dates,
        "close": close,
    })


@pytest.fixture
def strategy_row_and_mlflow(db_url_env: str, tmp_path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Seed a strategies row + point MLflow at a local file store."""
    # MLflow local file store (no server required for unit tests)
    mlflow_dir = tmp_path / "mlruns"
    mlflow_dir.mkdir()
    monkeypatch.setenv("PQ_MLFLOW_TRACKING_URI", mlflow_dir.as_uri())

    conn = psycopg2.connect(db_url_env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO strategies (name, entry_point, thresholds) "
                "VALUES (%s, %s, '{}'::jsonb) RETURNING id",
                (f"trivial-{uuid4().hex[:8]}", "trivial:main"),
            )
            sid = str(cur.fetchone()[0])
        conn.commit()
    finally:
        conn.close()
    return sid


def test_strategy_requires_name_class_attr() -> None:
    class Nameless(Strategy):
        def features(self, df): return df
        def target(self, df): return df["close"]
        def model(self): return LinearRegression()
    with pytest.raises(TypeError, match="name"):
        Nameless()


def test_train_and_validate_logs_mlflow_and_emits_modeltrained(
    db_url_env: str, strategy_row_and_mlflow: str
) -> None:
    sid = strategy_row_and_mlflow
    df = _synthetic_df(n_days=1500)

    with run.start(strategy_id=sid, as_of="2022-12-31") as r:
        strategy = _TrivialStrategy()
        summary = strategy.train_and_validate(df)

    assert summary["mlflow_run_id"]
    assert summary["mean_rmse"] > 0

    # Verify ModelTrained event on the audit chain
    conn = psycopg2.connect(db_url_env)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT event_type, payload FROM events WHERE run_id = %s ORDER BY created_at",
                (r.id,),
            )
            events = cur.fetchall()
        event_types = [e["event_type"] for e in events]
        assert "RunStarted" in event_types
        assert "ModelTrained" in event_types
        mt = [e for e in events if e["event_type"] == "ModelTrained"][0]
        assert mt["payload"]["strategy_name"] == "trivial"
        assert mt["payload"]["mlflow_run_id"] == summary["mlflow_run_id"]
    finally:
        conn.close()


def test_train_and_validate_raises_on_too_few_folds(
    db_url_env: str, strategy_row_and_mlflow: str
) -> None:
    sid = strategy_row_and_mlflow
    df = _synthetic_df(n_days=200)  # too short for 3y train + 8 folds

    with run.start(strategy_id=sid, as_of="2020-01-01"):
        strategy = _TrivialStrategy()
        with pytest.raises(ValueError, match="fold"):
            strategy.train_and_validate(df)
