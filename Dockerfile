# syntax=docker/dockerfile:1.7
# Single image. Role selected at startup via ROLE env var.
#
# Three stages:
#   1. `web-builder`  — builds the React SPA
#   2. `py-builder`   — installs Python deps via uv
#   3. `runtime`      — Debian slim runtime, copies app code + compiled SPA

# ---------- Stage 1: Build the SPA ----------
FROM node:22-alpine AS web-builder
ENV PNPM_HOME=/pnpm PATH=/pnpm:$PATH
RUN corepack enable && corepack prepare pnpm@10.33.0 --activate
WORKDIR /src
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json apps/web/
RUN pnpm install --frozen-lockfile --filter web
COPY apps/web ./apps/web
RUN pnpm --filter web build

# ---------- Stage 2: Python deps ----------
FROM python:3.12-slim AS py-builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_SYSTEM_PYTHON=1
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv
WORKDIR /app
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*
COPY apps/api/pyproject.toml apps/api/uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project || uv sync --no-dev --no-install-project
COPY apps/api/app ./app
COPY apps/api/migrations ./migrations
COPY apps/api/alembic.ini ./

# ---------- Stage 3: Runtime ----------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ROLE=api \
    STATIC_DIR=/app/static \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 libgomp1 dumb-init curl \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --uid 10001 --create-home --shell /bin/bash app

WORKDIR /app
COPY --from=py-builder --chown=app:app /app /app
COPY --from=web-builder --chown=app:app /src/apps/web/dist /app/static

USER app

EXPOSE 8000 8001 8080

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/bin/sh", "-c", "\
  case \"$ROLE\" in \
    api)                  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 ;; \
    bff)                  exec uvicorn app.bff.main:app --host 0.0.0.0 --port 8080 ;; \
    idp)                  exec uvicorn app.idp.main:app --host 0.0.0.0 --port 8001 ;; \
    worker-proj-ui)       exec python -m app.workers.proj_ui ;; \
    worker-training)      exec python -m app.workers.training ;; \
    worker-pipeline-bronze) exec python -m app.workers.pipeline_bronze ;; \
    worker-pipeline-silver) exec python -m app.workers.pipeline_silver ;; \
    scheduler)            exec python -m app.scheduler ;; \
    bridge-pgmq-http)     exec python -m app.workers.bridge ;; \
    *) echo \"unknown ROLE: $ROLE\" >&2; exit 2 ;; \
  esac"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8000/internal/health || \
      curl -fsS http://localhost:8080/internal/health || \
      curl -fsS http://localhost:8001/jwks || exit 1
