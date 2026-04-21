# syntax=docker/dockerfile:1.7
# Single image. Role selected at startup via ROLE env var.

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_SYSTEM_PYTHON=1

# Install uv (Astral). Pinned to a known-good release.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

FROM base AS builder
WORKDIR /app
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project || uv sync --no-dev --no-install-project

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ROLE=api \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 libgomp1 dumb-init curl \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --uid 10001 --create-home --shell /bin/bash app

WORKDIR /app
COPY --from=builder --chown=app:app /app /app

USER app

EXPOSE 8000

# Lightweight dispatcher: inspect ROLE and exec the correct command.
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
  CMD curl -fsS http://localhost:8000/internal/health || exit 1
