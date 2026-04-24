-- Enable required extensions at DB init
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- pgmq is installed in a subsequent migration (requires the extension package;
-- Postgres image includes it via the tembo image used in compose).

-- Separate database for MLflow's metadata. MLflow manages its own Alembic
-- migrations and would collide with our `qp` database's `alembic_version`
-- table if both shared one DB (discovered in M1 HIL on 2026-04-24).
CREATE DATABASE mlflow;
