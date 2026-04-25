# MLflow 3.11.1 (released 2026-04-08). Bumped from 2.16.0 because 2.x's
# pydantic / utcnow / pandas-copy deprecation warnings — emitted by
# MLflow's own internals against its deps — were resolved in 3.x once
# pydantic 1.x support was dropped (mlflow/mlflow#11203). Server
# auto-runs alembic migrations against the postgres backend on first
# boot of the new version (mlflow/mlflow#1948); the local `mlflow`
# database holds only HIL state, so an in-place upgrade is safe.
FROM ghcr.io/mlflow/mlflow:v3.11.1
RUN pip install --no-cache-dir psycopg2-binary==2.9.9 boto3==1.35.36
