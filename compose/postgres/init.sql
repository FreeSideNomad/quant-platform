-- Enable required extensions at DB init
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- pgmq is installed in a subsequent migration (requires the extension package;
-- Postgres image includes it via the tembo image used in compose).
