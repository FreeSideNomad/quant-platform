-- Creates a dedicated `mlflow` database alongside the main `quant` db.
-- MLflow manages its own schema in this database; the app's Alembic works only in `quant`.
CREATE DATABASE mlflow OWNER quant;
