-- Creates a dedicated `dagster` database alongside the main `quant` db.
-- Dagster manages its own schema (runs, event_log, schedule_ticks) in this
-- database via dagster-postgres. This avoids alembic_version table collisions
-- with the app's own Alembic migrations which run in the `quant` database.
CREATE DATABASE dagster OWNER quant;
