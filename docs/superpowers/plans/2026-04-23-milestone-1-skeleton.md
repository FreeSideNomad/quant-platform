# Milestone 1 — Skeleton + Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the monorepo skeleton with a `qp up` / `qp down` / `qp doctor` CLI, a docker-compose stack (Postgres + MinIO + MLflow + FastAPI placeholder + mock OIDC), Alembic initialized, and a UI placeholder — enough that a fresh clone can reach "all services healthy" in <5 minutes.

**Architecture:** Monorepo with `apps/api` (FastAPI), `apps/ui` (React/Vite placeholder), `apps/accounts` (stub), `packages/sdk` (Python SDK + `qp` CLI). One Docker image, multi-role via `SERVICE_ROLE` env var. docker-compose orchestrates local dev. Alembic manages schema. `qp` CLI wraps `docker compose` idiomatically.

**Tech Stack:** Python 3.12+, uv, FastAPI, SQLAlchemy 2 async, asyncpg, Alembic, Polars (lts-cpu), Pydantic v2, pytest, testcontainers, Docker, docker-compose, React 19, Vite, pnpm, Typer (CLI framework).

**Milestone DoD (from spec §9 M1):** Fresh laptop goes from `git clone` to functioning skeleton in <5 minutes. HIL script passes cleanly.

**Scope boundaries:**
- In scope: skeleton directories, three CLI commands (`up`, `down`, `doctor`), docker-compose with Postgres+MinIO+MLflow+API+UI+mock-OIDC, FastAPI `/health` endpoint, Alembic initialized (empty migration), integration test via testcontainers, E2E "compose up" health-check test, M1 HIL script doc.
- Out of scope for M1: any SDK surface beyond CLI stubs, strategy loading, validation math (M2), MLflow alias logic, serving role, authentication (M7), real UI screens (M5), accounts service (M7). Placeholders only.

**Self-review at end of plan: §Self-Review**

---

## File Structure (created by this milestone)

```
quant-platform/
├── apps/
│   ├── api/
│   │   ├── pyproject.toml                # API service dependencies
│   │   ├── src/api/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                   # FastAPI app + /health endpoint
│   │   │   └── settings.py               # Pydantic settings (env-var-driven)
│   │   ├── migrations/
│   │   │   ├── env.py                    # Alembic env
│   │   │   ├── script.py.mako
│   │   │   └── versions/
│   │   │       └── 0001_initial.py       # empty initial migration
│   │   ├── alembic.ini
│   │   ├── Dockerfile                    # multi-role image
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── conftest.py
│   │       ├── test_health.py            # unit: /health returns ok
│   │       └── test_compose_stack.py     # integration: testcontainers
├── apps/
│   ├── ui/
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   ├── tsconfig.json
│   │   ├── index.html
│   │   ├── src/
│   │   │   ├── main.tsx                  # React entry
│   │   │   └── App.tsx                   # placeholder "platform coming soon" + /health probe
│   │   └── public/
│   └── accounts/
│       └── README.md                     # placeholder (built in M7)
├── packages/
│   └── sdk/
│       ├── pyproject.toml                # quantplatform package (SDK + qp CLI)
│       ├── src/quantplatform/
│       │   ├── __init__.py
│       │   ├── cli/
│       │   │   ├── __init__.py
│       │   │   ├── main.py               # typer app entry point
│       │   │   ├── up.py                 # qp up
│       │   │   ├── down.py               # qp down
│       │   │   └── doctor.py             # qp doctor
│       │   └── sdk/
│       │       └── __init__.py           # placeholder (built in M3)
│       └── tests/
│           ├── __init__.py
│           ├── conftest.py
│           ├── test_cli_up.py
│           ├── test_cli_down.py
│           └── test_cli_doctor.py
├── compose/
│   ├── postgres/init.sql                 # pgmq + pgcrypto extensions
│   └── mock-oidc/                        # static HTML + Dockerfile
│       ├── Dockerfile
│       └── app.py
├── docs/
│   ├── superpowers/
│   │   ├── specs/                        # (already exists)
│   │   └── plans/                        # (already exists)
│   └── milestones/
│       └── M1/
│           └── hil.md                    # M1 HIL checkpoint script
├── docker-compose.yml                    # main compose file
├── pyproject.toml                        # workspace root (uv workspace)
├── uv.lock
├── package.json                          # pnpm workspace root
├── pnpm-workspace.yaml
└── .env.example
```

**Rationale for this shape:**
- `apps/` holds deployables (containerized services).
- `packages/sdk` holds the library shared across deployables — single wheel, two entry points (`import quantplatform` and `qp` CLI).
- `compose/` holds static config for compose services (not per-app).
- `docs/milestones/M<n>/hil.md` is the HIL checkpoint doc template the spec mandates.
- uv workspace at root so `uv sync` installs all Python deps in one lockfile.
- pnpm workspace for frontend packages.

---

## Task 1: Initialize monorepo root workspace files

**Files:**
- Create: `pyproject.toml` (uv workspace root)
- Create: `package.json` (pnpm workspace root)
- Create: `pnpm-workspace.yaml`
- Create: `.env.example`

- [ ] **Step 1: Create root `pyproject.toml` defining uv workspace**

Write file `pyproject.toml`:
```toml
[project]
name = "quant-platform"
version = "0.0.0"
description = "Quant Platform monorepo root"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["apps/api", "packages/sdk"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "ASYNC", "SIM"]

[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "strict"
```

- [ ] **Step 2: Create root `package.json` defining pnpm workspace**

Write file `package.json`:
```json
{
  "name": "quant-platform",
  "version": "0.0.0",
  "private": true,
  "packageManager": "pnpm@9.12.0"
}
```

- [ ] **Step 3: Create `pnpm-workspace.yaml`**

Write file `pnpm-workspace.yaml`:
```yaml
packages:
  - "apps/ui"
```

- [ ] **Step 4: Create `.env.example`**

Write file `.env.example`:
```
# Postgres
POSTGRES_USER=qp
POSTGRES_PASSWORD=qp
POSTGRES_DB=qp
DATABASE_URL=postgresql+asyncpg://qp:qp@localhost:5432/qp

# MinIO (S3-compatible)
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET_DEFAULT=qp-artifacts

# MLflow
MLFLOW_TRACKING_URI=http://localhost:5000

# Mock OIDC
OIDC_ISSUER=http://localhost:4444

# Service role (for single-image-multi-role)
SERVICE_ROLE=api
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml package.json pnpm-workspace.yaml .env.example
git commit -m "feat(M1-1): initialize uv+pnpm workspace roots"
```

---

## Task 2: SDK package scaffold with CLI entry point

**Files:**
- Create: `packages/sdk/pyproject.toml`
- Create: `packages/sdk/src/quantplatform/__init__.py`
- Create: `packages/sdk/src/quantplatform/cli/__init__.py`
- Create: `packages/sdk/src/quantplatform/cli/main.py`
- Create: `packages/sdk/src/quantplatform/sdk/__init__.py`
- Create: `packages/sdk/tests/__init__.py`
- Create: `packages/sdk/tests/conftest.py`

- [ ] **Step 1: Write `packages/sdk/pyproject.toml`**

```toml
[project]
name = "quantplatform"
version = "0.1.0"
description = "Quant Platform SDK + qp CLI"
requires-python = ">=3.12"
dependencies = [
  "typer>=0.12",
  "rich>=13.7",
  "httpx>=0.27",
  "pydantic>=2.8",
  "polars-lts-cpu>=1.8",
]

[project.scripts]
qp = "quantplatform.cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/quantplatform"]

[dependency-groups]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "pytest-cov>=5.0",
  "ruff>=0.7",
  "pyright>=1.1.380",
]
```

- [ ] **Step 2: Create package `__init__.py` files**

Write `packages/sdk/src/quantplatform/__init__.py`:
```python
"""Quant Platform SDK."""
__version__ = "0.1.0"
```

Write `packages/sdk/src/quantplatform/cli/__init__.py`:
```python
"""qp CLI entry point."""
```

Write `packages/sdk/src/quantplatform/sdk/__init__.py`:
```python
"""Quant Platform SDK (to be built in M3)."""
```

Write `packages/sdk/tests/__init__.py`:
```python
```

- [ ] **Step 3: Write failing test for `qp --version`**

Write `packages/sdk/tests/conftest.py`:
```python
"""Shared test fixtures for the quantplatform package."""
import pytest
from typer.testing import CliRunner

@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
```

Write `packages/sdk/tests/test_cli_version.py`:
```python
from quantplatform import __version__
from quantplatform.cli.main import app


def test_qp_version(runner) -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd packages/sdk && uv run pytest tests/test_cli_version.py -v`

Expected: FAIL (`app` does not exist; import error).

- [ ] **Step 5: Implement minimal CLI entry point**

Write `packages/sdk/src/quantplatform/cli/main.py`:
```python
"""qp CLI entry point."""
from __future__ import annotations

import typer

from quantplatform import __version__

app = typer.Typer(
    name="qp",
    help="Quant Platform CLI — local stack and strategy workflows.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"qp {__version__}")
        raise typer.Exit(code=0)


@app.callback()
def root(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show qp version and exit.",
    ),
) -> None:
    """qp — Quant Platform CLI."""
```

- [ ] **Step 6: Install workspace and re-run test**

From repo root:
```bash
uv sync
cd packages/sdk && uv run pytest tests/test_cli_version.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/sdk/ pyproject.toml
git commit -m "feat(M1-2): scaffold quantplatform package and qp CLI entry point"
```

---

## Task 3: Root docker-compose.yml with service placeholders

**Files:**
- Create: `docker-compose.yml`
- Create: `compose/postgres/init.sql`

- [ ] **Step 1: Write `compose/postgres/init.sql`**

Write `compose/postgres/init.sql`:
```sql
-- Enable required extensions at DB init
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- pgmq is installed in a subsequent migration (requires the extension package;
-- Postgres image includes it via the tembo image used in compose).
```

- [ ] **Step 2: Write `docker-compose.yml` with service stubs**

Write `docker-compose.yml`:
```yaml
services:
  postgres:
    image: quay.io/tembo/pg16-pgmq:latest
    container_name: qp-postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-qp}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-qp}
      POSTGRES_DB: ${POSTGRES_DB:-qp}
    volumes:
      - qp-postgres-data:/var/lib/postgresql/data
      - ./compose/postgres/init.sql:/docker-entrypoint-initdb.d/00-init.sql:ro
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-qp} -d ${POSTGRES_DB:-qp}"]
      interval: 3s
      timeout: 3s
      retries: 20

  minio:
    image: quay.io/minio/minio:RELEASE.2024-09-22T00-33-43Z
    container_name: qp-minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${S3_ACCESS_KEY:-minioadmin}
      MINIO_ROOT_PASSWORD: ${S3_SECRET_KEY:-minioadmin}
    volumes:
      - qp-minio-data:/data
    ports:
      - "9000:9000"
      - "9001:9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/ready"]
      interval: 3s
      timeout: 3s
      retries: 20

  minio-init:
    image: quay.io/minio/mc:RELEASE.2024-09-16T17-43-14Z
    container_name: qp-minio-init
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set qp http://minio:9000 ${S3_ACCESS_KEY:-minioadmin} ${S3_SECRET_KEY:-minioadmin} &&
      mc mb -p qp/${S3_BUCKET_DEFAULT:-qp-artifacts} &&
      mc mb -p qp/mlflow-artifacts &&
      exit 0
      "

  mlflow:
    image: ghcr.io/mlflow/mlflow:v2.16.0
    container_name: qp-mlflow
    depends_on:
      postgres:
        condition: service_healthy
      minio-init:
        condition: service_completed_successfully
    environment:
      MLFLOW_BACKEND_STORE_URI: postgresql+psycopg2://${POSTGRES_USER:-qp}:${POSTGRES_PASSWORD:-qp}@postgres:5432/${POSTGRES_DB:-qp}
      MLFLOW_DEFAULT_ARTIFACT_ROOT: s3://mlflow-artifacts/
      MLFLOW_S3_ENDPOINT_URL: http://minio:9000
      AWS_ACCESS_KEY_ID: ${S3_ACCESS_KEY:-minioadmin}
      AWS_SECRET_ACCESS_KEY: ${S3_SECRET_KEY:-minioadmin}
    command: >
      mlflow server
      --host 0.0.0.0
      --port 5000
      --backend-store-uri postgresql+psycopg2://${POSTGRES_USER:-qp}:${POSTGRES_PASSWORD:-qp}@postgres:5432/${POSTGRES_DB:-qp}
      --default-artifact-root s3://mlflow-artifacts/
    ports:
      - "5000:5000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 3s
      timeout: 3s
      retries: 20

  mock-oidc:
    build:
      context: ./compose/mock-oidc
    container_name: qp-mock-oidc
    ports:
      - "4444:4444"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4444/.well-known/openid-configuration"]
      interval: 3s
      timeout: 3s
      retries: 20

  api:
    build:
      context: ./apps/api
    container_name: qp-api
    depends_on:
      postgres:
        condition: service_healthy
      mlflow:
        condition: service_healthy
    environment:
      SERVICE_ROLE: api
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-qp}:${POSTGRES_PASSWORD:-qp}@postgres:5432/${POSTGRES_DB:-qp}
      S3_ENDPOINT_URL: http://minio:9000
      S3_ACCESS_KEY: ${S3_ACCESS_KEY:-minioadmin}
      S3_SECRET_KEY: ${S3_SECRET_KEY:-minioadmin}
      MLFLOW_TRACKING_URI: http://mlflow:5000
      OIDC_ISSUER: http://mock-oidc:4444
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 3s
      timeout: 3s
      retries: 20

  ui:
    build:
      context: ./apps/ui
    container_name: qp-ui
    depends_on:
      api:
        condition: service_healthy
    ports:
      - "5173:5173"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5173"]
      interval: 3s
      timeout: 3s
      retries: 20

volumes:
  qp-postgres-data:
  qp-minio-data:
```

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml compose/postgres/init.sql
git commit -m "feat(M1-3): docker-compose with postgres, minio, mlflow, mock-oidc, api, ui service stubs"
```

---

## Task 4: Mock OIDC service (minimal static issuer)

**Files:**
- Create: `compose/mock-oidc/Dockerfile`
- Create: `compose/mock-oidc/app.py`

Mock OIDC is a tiny FastAPI app that serves a static `/.well-known/openid-configuration`. No real OAuth — MVP UI uses a mock session cookie set by `qp up --open-browser` later (M5 topic). For M1, the container just needs to respond healthy.

- [ ] **Step 1: Write `compose/mock-oidc/app.py`**

```python
from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Mock OIDC (M1 placeholder)")


@app.get("/.well-known/openid-configuration")
def openid_configuration() -> dict[str, str]:
    """Minimal OIDC discovery document — enough to pass a healthcheck."""
    return {
        "issuer": "http://localhost:4444",
        "authorization_endpoint": "http://localhost:4444/authorize",
        "token_endpoint": "http://localhost:4444/token",
        "jwks_uri": "http://localhost:4444/jwks",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 2: Write `compose/mock-oidc/Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.115.0 uvicorn==0.30.6 curl
COPY app.py .
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
EXPOSE 4444
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "4444"]
```

- [ ] **Step 3: Commit**

```bash
git add compose/mock-oidc/
git commit -m "feat(M1-4): minimal mock OIDC service for local dev"
```

---

## Task 5: FastAPI API service with /health endpoint

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/src/api/__init__.py`
- Create: `apps/api/src/api/main.py`
- Create: `apps/api/src/api/settings.py`
- Create: `apps/api/Dockerfile`
- Create: `apps/api/tests/__init__.py`
- Create: `apps/api/tests/conftest.py`
- Create: `apps/api/tests/test_health.py`

- [ ] **Step 1: Write `apps/api/pyproject.toml`**

```toml
[project]
name = "qp-api"
version = "0.1.0"
description = "Quant Platform API service"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.8",
  "pydantic-settings>=2.4",
  "sqlalchemy[asyncio]>=2.0",
  "asyncpg>=0.29",
  "alembic>=1.13",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/api"]

[dependency-groups]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "httpx>=0.27",
  "testcontainers[postgres,minio]>=4.8",
]
```

- [ ] **Step 2: Write `apps/api/src/api/__init__.py`**

```python
"""Quant Platform API service."""
__version__ = "0.1.0"
```

- [ ] **Step 3: Write `apps/api/src/api/settings.py`**

```python
"""Application settings loaded from environment variables."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_role: str = Field(default="api", alias="SERVICE_ROLE")
    database_url: str = Field(
        default="postgresql+asyncpg://qp:qp@localhost:5432/qp", alias="DATABASE_URL"
    )
    mlflow_tracking_uri: str = Field(
        default="http://localhost:5000", alias="MLFLOW_TRACKING_URI"
    )


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Write failing test `apps/api/tests/test_health.py`**

Write `apps/api/tests/conftest.py`:
```python
"""Shared test fixtures."""
import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
```

Write `apps/api/tests/test_health.py`:
```python
def test_health_returns_ok(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["role"] == "api"


def test_health_includes_version(client) -> None:
    response = client.get("/health")
    assert "version" in response.json()
```

- [ ] **Step 5: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_health.py -v`

Expected: FAIL (`api.main` does not exist).

- [ ] **Step 6: Implement `apps/api/src/api/main.py`**

```python
"""FastAPI application entry point."""
from __future__ import annotations

from fastapi import FastAPI

from api import __version__
from api.settings import get_settings

settings = get_settings()

app = FastAPI(
    title="Quant Platform API",
    version=__version__,
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness + readiness probe."""
    return {
        "status": "ok",
        "role": settings.service_role,
        "version": __version__,
    }
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_health.py -v`

Expected: both tests PASS.

- [ ] **Step 8: Write `apps/api/Dockerfile`**

Multi-role image: role selected at runtime via `SERVICE_ROLE` env var. For M1, only `api` role is implemented; worker/serving roles come in later milestones.

```dockerfile
FROM python:3.12-slim AS base
WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# uv for dependency management
RUN pip install --no-cache-dir uv==0.4.23

# Copy project
COPY pyproject.toml ./
COPY src ./src

# Install deps
RUN uv pip install --system --no-cache .

# Entrypoint selects role at runtime
ENV SERVICE_ROLE=api
EXPOSE 8000

CMD ["sh", "-c", "\
  case \"$SERVICE_ROLE\" in \
    api) exec uvicorn api.main:app --host 0.0.0.0 --port 8000 ;; \
    worker_training) echo 'worker_training role — implemented in M3+' && sleep infinity ;; \
    worker_serving) echo 'worker_serving role — implemented in M6' && sleep infinity ;; \
    *) echo \"Unknown SERVICE_ROLE: $SERVICE_ROLE\" && exit 1 ;; \
  esac \
"]
```

- [ ] **Step 9: Commit**

```bash
git add apps/api/
git commit -m "feat(M1-5): FastAPI /health endpoint with multi-role Dockerfile"
```

---

## Task 6: Alembic initialization with empty migration

**Files:**
- Create: `apps/api/alembic.ini`
- Create: `apps/api/migrations/env.py`
- Create: `apps/api/migrations/script.py.mako`
- Create: `apps/api/migrations/versions/0001_initial.py`
- Create: `apps/api/tests/test_alembic_roundtrip.py`

- [ ] **Step 1: Write `apps/api/alembic.ini`**

```ini
[alembic]
script_location = migrations
prepend_sys_path = src
sqlalchemy.url = postgresql+psycopg2://qp:qp@localhost:5432/qp

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: Write `apps/api/migrations/env.py`**

```python
"""Alembic environment: runs migrations with a synchronous (psycopg2) URL."""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use env DATABASE_URL if set (but convert asyncpg -> psycopg2 for alembic).
db_url = os.environ.get("DATABASE_URL")
if db_url:
    db_url = db_url.replace("+asyncpg", "+psycopg2")
    config.set_main_option("sqlalchemy.url", db_url)

target_metadata = None  # no ORM models in M1; migrations are hand-written


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: Write `apps/api/migrations/script.py.mako`**

```
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from __future__ import annotations

from alembic import op

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 4: Write empty initial migration `apps/api/migrations/versions/0001_initial.py`**

```python
"""initial (empty) schema — subsequent migrations land in later milestones

Revision ID: 0001
Revises:
Create Date: 2026-04-23 00:00:00.000000

"""
from __future__ import annotations

from alembic import op  # noqa: F401

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Initial migration: creates pgmq extension; no tables yet."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pgmq CASCADE;")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pgmq CASCADE;")
```

- [ ] **Step 5: Add psycopg2 to api dev deps**

Edit `apps/api/pyproject.toml`, in `[dependency-groups] dev`, add `psycopg2-binary>=2.9` (alembic uses sync driver):
```toml
[dependency-groups]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "httpx>=0.27",
  "testcontainers[postgres,minio]>=4.8",
  "psycopg2-binary>=2.9",
]
```

- [ ] **Step 6: Write migration roundtrip test `apps/api/tests/test_alembic_roundtrip.py`**

```python
"""Verify alembic downgrade base && upgrade head works on a clean DB.

Port of the `testcontainers migration roundtrip` pattern from MVP-A
(LESSONS.md §worth-keeping).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from testcontainers.postgres import PostgresContainer

API_DIR = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def postgres_container():
    # Use the tembo pg16-pgmq image so the pgmq extension is available.
    with PostgresContainer("quay.io/tembo/pg16-pgmq:latest", driver="psycopg2") as pg:
        yield pg


def _run_alembic(args: list[str], db_url: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=API_DIR,
        env={"DATABASE_URL": db_url, "PATH": __import__("os").environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
    )


def test_alembic_upgrade_head(postgres_container) -> None:
    db_url = postgres_container.get_connection_url()  # psycopg2 URL
    result = _run_alembic(["upgrade", "head"], db_url)
    assert result.returncode == 0, result.stderr


def test_alembic_downgrade_base_then_upgrade_head(postgres_container) -> None:
    db_url = postgres_container.get_connection_url()
    result = _run_alembic(["downgrade", "base"], db_url)
    assert result.returncode == 0, result.stderr
    result = _run_alembic(["upgrade", "head"], db_url)
    assert result.returncode == 0, result.stderr
```

- [ ] **Step 7: Run the test**

Run: `cd apps/api && uv run pytest tests/test_alembic_roundtrip.py -v`

Expected: both tests PASS. (Requires Docker running locally for testcontainers.)

- [ ] **Step 8: Commit**

```bash
git add apps/api/alembic.ini apps/api/migrations/ apps/api/pyproject.toml apps/api/tests/test_alembic_roundtrip.py
git commit -m "feat(M1-6): alembic scaffold with empty initial migration and roundtrip test"
```

---

## Task 7: UI placeholder (Vite + React + TanStack)

**Files:**
- Create: `apps/ui/package.json`
- Create: `apps/ui/vite.config.ts`
- Create: `apps/ui/tsconfig.json`
- Create: `apps/ui/tsconfig.node.json`
- Create: `apps/ui/index.html`
- Create: `apps/ui/src/main.tsx`
- Create: `apps/ui/src/App.tsx`
- Create: `apps/ui/Dockerfile`

- [ ] **Step 1: Write `apps/ui/package.json`**

```json
{
  "name": "qp-ui",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0 --port 5173",
    "build": "tsc && vite build",
    "preview": "vite preview --host 0.0.0.0 --port 5173"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "@tanstack/react-router": "^1.77.0"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.3",
    "typescript": "^5.6.3",
    "vite": "^5.4.9"
  }
}
```

- [ ] **Step 2: Write `apps/ui/vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
```

- [ ] **Step 3: Write `apps/ui/tsconfig.json` and `tsconfig.node.json`**

Write `apps/ui/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Write `apps/ui/tsconfig.node.json`:
```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: Write `apps/ui/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Quant Platform</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Write `apps/ui/src/main.tsx`**

```typescript
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 6: Write `apps/ui/src/App.tsx`**

```typescript
import { useEffect, useState } from "react";

interface HealthResponse {
  status: string;
  role: string;
  version: string;
}

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then(setHealth)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: 32, maxWidth: 720 }}>
      <h1>Quant Platform</h1>
      <p>Skeleton (M1). Real UI ships in M5.</p>
      {error && <pre style={{ color: "crimson" }}>{error}</pre>}
      {health && (
        <pre style={{ background: "#f4f4f4", padding: 16 }}>
          {JSON.stringify(health, null, 2)}
        </pre>
      )}
    </main>
  );
}
```

- [ ] **Step 7: Write `apps/ui/Dockerfile`**

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
COPY pnpm-lock.yaml* ./
RUN pnpm install
COPY . .
RUN pnpm build

FROM nginx:1.27-alpine
RUN apk add --no-cache curl
COPY --from=build /app/dist /usr/share/nginx/html
COPY <<'NGINX' /etc/nginx/conf.d/default.conf
server {
    listen 5173;
    location / {
        root /usr/share/nginx/html;
        try_files $uri /index.html;
    }
    location /api/ {
        proxy_pass http://api:8000/;
    }
}
NGINX
EXPOSE 5173
CMD ["nginx", "-g", "daemon off;"]
```

- [ ] **Step 8: Verify build runs locally**

Run:
```bash
cd apps/ui && pnpm install && pnpm build
```

Expected: `dist/` produced without errors.

- [ ] **Step 9: Commit**

```bash
git add apps/ui/
git commit -m "feat(M1-7): UI placeholder (Vite + React + TanStack) with /health probe"
```

---

## Task 8: `qp up` CLI command

**Files:**
- Modify: `packages/sdk/src/quantplatform/cli/main.py`
- Create: `packages/sdk/src/quantplatform/cli/up.py`
- Create: `packages/sdk/tests/test_cli_up.py`

- [ ] **Step 1: Write failing test `packages/sdk/tests/test_cli_up.py`**

```python
"""Unit tests for `qp up` — mocks docker compose subprocess."""
from __future__ import annotations

from unittest.mock import patch

from quantplatform.cli.main import app


def test_qp_up_invokes_docker_compose(runner) -> None:
    with patch("quantplatform.cli.up.subprocess.run") as run:
        run.return_value.returncode = 0
        result = runner.invoke(app, ["up"])
    assert result.exit_code == 0
    run.assert_called_once()
    args = run.call_args.args[0]
    assert args[:2] == ["docker", "compose"]
    assert "up" in args
    assert "-d" in args


def test_qp_up_propagates_nonzero_exit(runner) -> None:
    with patch("quantplatform.cli.up.subprocess.run") as run:
        run.return_value.returncode = 2
        result = runner.invoke(app, ["up"])
    assert result.exit_code == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/sdk && uv run pytest tests/test_cli_up.py -v`

Expected: FAIL — `quantplatform.cli.up` does not exist.

- [ ] **Step 3: Implement `packages/sdk/src/quantplatform/cli/up.py`**

```python
"""`qp up` — start the local stack via docker compose."""
from __future__ import annotations

import subprocess

import typer
from rich.console import Console

console = Console()


def up() -> None:
    """Start the local Quant Platform stack (docker compose up -d)."""
    console.print("[bold]Starting Quant Platform stack...[/bold]")
    result = subprocess.run(
        ["docker", "compose", "up", "-d"],
        check=False,
    )
    if result.returncode != 0:
        console.print("[red]docker compose up failed.[/red]")
        raise typer.Exit(code=result.returncode)
    console.print("[green]Stack started.[/green] UI at http://localhost:5173")
```

- [ ] **Step 4: Register `up` in `packages/sdk/src/quantplatform/cli/main.py`**

Modify `packages/sdk/src/quantplatform/cli/main.py` — add this line below the existing imports and above the `app = typer.Typer(...)` definition:

```python
from quantplatform.cli.up import up as up_command
```

Then after the `root` callback definition, add:

```python
app.command(name="up", help="Start the local Quant Platform stack.")(up_command)
```

Full file should read:

```python
"""qp CLI entry point."""
from __future__ import annotations

import typer

from quantplatform import __version__
from quantplatform.cli.up import up as up_command

app = typer.Typer(
    name="qp",
    help="Quant Platform CLI — local stack and strategy workflows.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"qp {__version__}")
        raise typer.Exit(code=0)


@app.callback()
def root(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show qp version and exit.",
    ),
) -> None:
    """qp — Quant Platform CLI."""


app.command(name="up", help="Start the local Quant Platform stack.")(up_command)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd packages/sdk && uv run pytest tests/test_cli_up.py -v`

Expected: both tests PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/sdk/src/quantplatform/cli/up.py packages/sdk/src/quantplatform/cli/main.py packages/sdk/tests/test_cli_up.py
git commit -m "feat(M1-8): qp up wraps docker compose up -d"
```

---

## Task 9: `qp down` CLI command

**Files:**
- Modify: `packages/sdk/src/quantplatform/cli/main.py`
- Create: `packages/sdk/src/quantplatform/cli/down.py`
- Create: `packages/sdk/tests/test_cli_down.py`

- [ ] **Step 1: Write failing test `packages/sdk/tests/test_cli_down.py`**

```python
"""Unit tests for `qp down` — mocks docker compose subprocess."""
from __future__ import annotations

from unittest.mock import patch

from quantplatform.cli.main import app


def test_qp_down_invokes_docker_compose(runner) -> None:
    with patch("quantplatform.cli.down.subprocess.run") as run:
        run.return_value.returncode = 0
        result = runner.invoke(app, ["down"])
    assert result.exit_code == 0
    run.assert_called_once()
    args = run.call_args.args[0]
    assert args[:2] == ["docker", "compose"]
    assert "down" in args


def test_qp_down_does_not_remove_volumes_by_default(runner) -> None:
    with patch("quantplatform.cli.down.subprocess.run") as run:
        run.return_value.returncode = 0
        runner.invoke(app, ["down"])
    args = run.call_args.args[0]
    assert "-v" not in args
    assert "--volumes" not in args
```

- [ ] **Step 2: Run test — expect failure**

Run: `cd packages/sdk && uv run pytest tests/test_cli_down.py -v`

Expected: FAIL — `quantplatform.cli.down` does not exist.

- [ ] **Step 3: Implement `packages/sdk/src/quantplatform/cli/down.py`**

```python
"""`qp down` — stop the local stack. Data volumes are preserved by default."""
from __future__ import annotations

import subprocess

import typer
from rich.console import Console

console = Console()


def down() -> None:
    """Stop the local Quant Platform stack (docker compose down; volumes preserved)."""
    console.print("[bold]Stopping Quant Platform stack...[/bold]")
    result = subprocess.run(
        ["docker", "compose", "down"],
        check=False,
    )
    if result.returncode != 0:
        console.print("[red]docker compose down failed.[/red]")
        raise typer.Exit(code=result.returncode)
    console.print("[green]Stack stopped.[/green] Data volumes preserved.")
```

- [ ] **Step 4: Register `down` in `main.py`**

Modify `packages/sdk/src/quantplatform/cli/main.py` — add import and command registration:

Add with existing `up` import:
```python
from quantplatform.cli.down import down as down_command
```

Add after the `up` command registration:
```python
app.command(name="down", help="Stop the local Quant Platform stack (volumes preserved).")(down_command)
```

- [ ] **Step 5: Run test to verify pass**

Run: `cd packages/sdk && uv run pytest tests/test_cli_down.py -v`

Expected: both tests PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/sdk/src/quantplatform/cli/down.py packages/sdk/src/quantplatform/cli/main.py packages/sdk/tests/test_cli_down.py
git commit -m "feat(M1-9): qp down wraps docker compose down (volumes preserved)"
```

---

## Task 10: `qp doctor` CLI command

**Files:**
- Modify: `packages/sdk/src/quantplatform/cli/main.py`
- Create: `packages/sdk/src/quantplatform/cli/doctor.py`
- Create: `packages/sdk/tests/test_cli_doctor.py`

`qp doctor` verifies local prerequisites: Docker daemon reachable, `docker compose` subcommand present, Python version ≥3.12, required ports free (5432, 9000, 9001, 5000, 4444, 8000, 5173).

- [ ] **Step 1: Write failing test `packages/sdk/tests/test_cli_doctor.py`**

```python
"""Unit tests for `qp doctor` — mocks all probes."""
from __future__ import annotations

from unittest.mock import patch

from quantplatform.cli.main import app


def test_qp_doctor_all_checks_pass(runner) -> None:
    with (
        patch("quantplatform.cli.doctor._check_docker", return_value=(True, "Docker 27.3.1")),
        patch("quantplatform.cli.doctor._check_compose", return_value=(True, "Compose v2.29")),
        patch("quantplatform.cli.doctor._check_python", return_value=(True, "Python 3.12.5")),
        patch("quantplatform.cli.doctor._check_ports", return_value=(True, "All required ports free")),
    ):
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Docker 27.3.1" in result.stdout
    assert "All required ports free" in result.stdout


def test_qp_doctor_fails_on_missing_docker(runner) -> None:
    with (
        patch("quantplatform.cli.doctor._check_docker", return_value=(False, "Docker not installed")),
        patch("quantplatform.cli.doctor._check_compose", return_value=(True, "")),
        patch("quantplatform.cli.doctor._check_python", return_value=(True, "")),
        patch("quantplatform.cli.doctor._check_ports", return_value=(True, "")),
    ):
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "Docker not installed" in result.stdout


def test_qp_doctor_fails_on_port_conflict(runner) -> None:
    with (
        patch("quantplatform.cli.doctor._check_docker", return_value=(True, "")),
        patch("quantplatform.cli.doctor._check_compose", return_value=(True, "")),
        patch("quantplatform.cli.doctor._check_python", return_value=(True, "")),
        patch(
            "quantplatform.cli.doctor._check_ports",
            return_value=(False, "Port 8000 already in use"),
        ),
    ):
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "Port 8000 already in use" in result.stdout
```

- [ ] **Step 2: Run test — expect failure**

Run: `cd packages/sdk && uv run pytest tests/test_cli_doctor.py -v`

Expected: FAIL — `quantplatform.cli.doctor` does not exist.

- [ ] **Step 3: Implement `packages/sdk/src/quantplatform/cli/doctor.py`**

```python
"""`qp doctor` — verify local prerequisites."""
from __future__ import annotations

import shutil
import socket
import subprocess
import sys

import typer
from rich.console import Console

console = Console()

REQUIRED_PORTS: tuple[int, ...] = (5432, 9000, 9001, 5000, 4444, 8000, 5173)


def _check_docker() -> tuple[bool, str]:
    if shutil.which("docker") is None:
        return False, "Docker not installed"
    result = subprocess.run(
        ["docker", "--version"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return False, "Docker not responding"
    return True, result.stdout.strip()


def _check_compose() -> tuple[bool, str]:
    result = subprocess.run(
        ["docker", "compose", "version"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return False, "docker compose subcommand not available"
    return True, result.stdout.strip().splitlines()[0]


def _check_python() -> tuple[bool, str]:
    major, minor = sys.version_info[:2]
    version_str = f"Python {major}.{minor}.{sys.version_info.micro}"
    if (major, minor) < (3, 12):
        return False, f"{version_str} — need >=3.12"
    return True, version_str


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _check_ports() -> tuple[bool, str]:
    busy = [p for p in REQUIRED_PORTS if not _port_is_free(p)]
    if busy:
        return False, f"Port {busy[0]} already in use"
    return True, "All required ports free"


def doctor() -> None:
    """Verify Docker, compose, Python version, and port availability."""
    checks: list[tuple[str, tuple[bool, str]]] = [
        ("Docker", _check_docker()),
        ("Compose", _check_compose()),
        ("Python", _check_python()),
        ("Ports", _check_ports()),
    ]
    all_ok = all(ok for _, (ok, _) in checks)
    for name, (ok, detail) in checks:
        icon = "[green]OK[/green]" if ok else "[red]FAIL[/red]"
        console.print(f"{icon} {name}: {detail}")
    if not all_ok:
        raise typer.Exit(code=1)
```

- [ ] **Step 4: Register `doctor` in `main.py`**

Modify `packages/sdk/src/quantplatform/cli/main.py`:

Add import:
```python
from quantplatform.cli.doctor import doctor as doctor_command
```

Add command registration after `down`:
```python
app.command(name="doctor", help="Verify Docker, uv, Python, and free ports.")(doctor_command)
```

- [ ] **Step 5: Run test to verify pass**

Run: `cd packages/sdk && uv run pytest tests/test_cli_doctor.py -v`

Expected: all three tests PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/sdk/src/quantplatform/cli/doctor.py packages/sdk/src/quantplatform/cli/main.py packages/sdk/tests/test_cli_doctor.py
git commit -m "feat(M1-10): qp doctor verifies docker, compose, python, and ports"
```

---

## Task 11: Accounts placeholder

**Files:**
- Create: `apps/accounts/README.md`

- [ ] **Step 1: Write `apps/accounts/README.md`**

```markdown
# apps/accounts

Placeholder. The accounts service is implemented in milestone M7
(per `docs/superpowers/specs/2026-04-23-quant-mvp-design.md`).

For M1 it's intentionally empty — no docker-compose entry, no code —
because the MVP demo on a laptop does not require hosted telemetry or
OAuth login flows.
```

- [ ] **Step 2: Commit**

```bash
git add apps/accounts/
git commit -m "chore(M1-11): placeholder for accounts service (built in M7)"
```

---

## Task 12: Compose stack integration test

**Files:**
- Create: `tests/integration/test_compose_stack.py`
- Create: `tests/integration/conftest.py`
- Create: `tests/integration/__init__.py`
- Modify: root `pyproject.toml` — add integration test deps

The compose-stack test spins up the full local stack, waits for health, and tears it down. This is an E2E smoke test rather than a unit test.

- [ ] **Step 1: Add integration test deps to root `pyproject.toml`**

Modify `pyproject.toml` at the repo root — add a `[dependency-groups] integration` section:

```toml
[dependency-groups]
integration = [
  "pytest>=8.3",
  "httpx>=0.27",
  "tenacity>=9.0",
]
```

- [ ] **Step 2: Write `tests/integration/__init__.py` and `conftest.py`**

Write `tests/integration/__init__.py` (empty):
```python
```

Write `tests/integration/conftest.py`:
```python
"""Integration-test fixtures: bring up the compose stack once per session."""
from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent


@pytest.fixture(scope="session")
def compose_up() -> Iterator[None]:
    """Ensure the docker-compose stack is up for the duration of the test session."""
    subprocess.run(
        ["docker", "compose", "up", "-d", "--wait"],
        cwd=REPO_ROOT,
        check=True,
    )
    yield
    subprocess.run(
        ["docker", "compose", "down"],
        cwd=REPO_ROOT,
        check=True,
    )
```

- [ ] **Step 3: Write the smoke test `tests/integration/test_compose_stack.py`**

```python
"""End-to-end: bring up the full compose stack and verify all services healthy."""
from __future__ import annotations

import httpx
import pytest
from tenacity import retry, stop_after_delay, wait_fixed


@retry(stop=stop_after_delay(30), wait=wait_fixed(1), reraise=True)
def _get(url: str) -> httpx.Response:
    return httpx.get(url, timeout=5.0)


@pytest.mark.usefixtures("compose_up")
class TestComposeStack:
    def test_api_health(self) -> None:
        response = _get("http://localhost:8000/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_mlflow_health(self) -> None:
        response = _get("http://localhost:5000/health")
        assert response.status_code == 200

    def test_minio_health(self) -> None:
        response = _get("http://localhost:9000/minio/health/ready")
        assert response.status_code == 200

    def test_mock_oidc_health(self) -> None:
        response = _get("http://localhost:4444/.well-known/openid-configuration")
        assert response.status_code == 200
        assert response.json()["issuer"].startswith("http://localhost")

    def test_ui_root(self) -> None:
        response = _get("http://localhost:5173")
        assert response.status_code == 200
```

- [ ] **Step 4: Run the integration test**

Run from repo root:
```bash
uv run --group integration pytest tests/integration/ -v
```

Expected: all five tests PASS. (First run will build images; budget ~2-3 minutes.)

- [ ] **Step 5: Commit**

```bash
git add tests/integration/ pyproject.toml
git commit -m "test(M1-12): compose-stack integration smoke test"
```

---

## Task 13: M1 HIL checkpoint document

**Files:**
- Create: `docs/milestones/M1/hil.md`

- [ ] **Step 1: Write `docs/milestones/M1/hil.md`**

```markdown
# Milestone M1 — HIL Checkpoint

## Scope of this review

What landed:
- Monorepo skeleton (apps/api, apps/ui, apps/accounts placeholder, packages/sdk).
- `qp` CLI with `up`, `down`, `doctor` subcommands.
- `docker-compose.yml` with Postgres (pgmq) + MinIO + MLflow + FastAPI API + UI + mock OIDC.
- Alembic initialized with empty initial migration (creates pgmq extension).
- FastAPI `/health` endpoint returning `{status, role, version}`.
- UI placeholder that fetches `/api/health` and renders the response.
- Integration test (`tests/integration/test_compose_stack.py`) verifying all services respond.

What did NOT land (deliberately):
- Any SDK surface beyond CLI stubs. (M3)
- Validation math. (M2)
- MLflow alias wiring. (M4)
- Serving role. (M6)
- Real authentication. (M7)
- Real UI screens. (M5)

## Prerequisites

- Repo at commit `<sha>` (latest on `main` after Task 13)
- Docker Desktop (or equivalent) running
- Ports 4444, 5000, 5173, 5432, 8000, 9000, 9001 free
- uv installed (`curl -LsSf https://astral.sh/uv/install.sh | sh` if missing)

Automated tests all green:
- `uv run --group integration pytest tests/integration/ -v` → all PASS
- `cd apps/api && uv run pytest -v` → all PASS
- `cd packages/sdk && uv run pytest -v` → all PASS

## Script

1. **Clean-clone test**
   - On a second working directory (simulates a fresh laptop):
     ```bash
     git clone git@github.com:FreeSideNomad/quant-platform.git /tmp/qp-fresh
     cd /tmp/qp-fresh
     ```
   - Expected: clone completes without errors.

2. **Install the CLI**
   ```bash
   uv sync
   uv run qp --version
   ```
   - Expected: prints `qp 0.1.0`.

3. **Run qp doctor**
   ```bash
   uv run qp doctor
   ```
   - Expected: all four checks (Docker, Compose, Python, Ports) show `OK`. If any fail, address before continuing.

4. **Bring up the stack**
   ```bash
   uv run qp up
   ```
   - Expected: terminal shows `Starting Quant Platform stack...` then `Stack started. UI at http://localhost:5173`.
   - Budget: <90 seconds on a cold laptop (image pulls included).

5. **Verify all services**
   ```bash
   docker compose ps
   ```
   - Expected: every row shows `healthy` (postgres, minio, mlflow, mock-oidc, api, ui). The `minio-init` row is `exited (0)` — that's correct; it's a one-shot init job.

6. **Hit each service in a browser or curl**
   - `http://localhost:8000/health` — expect JSON `{"status":"ok","role":"api","version":"0.1.0"}`
   - `http://localhost:5000` — expect MLflow UI
   - `http://localhost:9001` — expect MinIO console (login: `minioadmin` / `minioadmin`)
   - `http://localhost:4444/.well-known/openid-configuration` — expect JSON with `issuer`
   - `http://localhost:5173` — expect "Quant Platform — Skeleton (M1)" placeholder, with `/api/health` response rendered

7. **State-persistence test**
   - `uv run qp down` — expected: stack stops gracefully; volumes preserved
   - `docker compose ps` — expected: no running containers
   - `uv run qp up` — expected: stack returns quickly (<30s; images and volumes reused)
   - Connect to Postgres: `psql postgresql://qp:qp@localhost:5432/qp -c "\\dx"` — expected: `pgmq` extension present (installed by migration during first boot). Extensions persist across `down` / `up`.

8. **`qp doctor` after boot**
   - `uv run qp doctor` — expected: some ports now show as in-use (API on 8000, UI on 5173, etc.); this is correct behavior when the stack is up. Confirm this matches spec-behavior expectations.

9. **Tear-down**
   - `uv run qp down`
   - `docker compose ps` — expected: nothing running.

## Decision points (HIL judgement)

- **Is `qp up` time acceptable?** Spec DoD says <5 minutes from clone to running stack. What did this laptop hit? Within budget?
- **Is the `qp doctor` output clear?** Does "Port 8000 already in use" when the stack is up feel correct, or should doctor distinguish "our own stack is using it" from "someone else has it"?
- **Is the UI placeholder useful, or distracting?** A placeholder reading "real UI ships in M5" sets the expectation; an empty page does not. Is the message right?
- **Does the clean-clone flow work for a Linux user as well as a Mac user?** If only tested on one, note whether the other is a risk.

## Sign-off

- [ ] Automated tests green (unit + integration)
- [ ] Script ran to completion without surprises
- [ ] Decision points resolved (see notes below)
- [ ] User approves proceeding to M2 (validation math port)

## Defects found

(Add below; classify each as MUST-FIX-BEFORE-M2 / DEFER-TO-V2 / SPEC-UPDATE)

## Spec / plan updates triggered

(If any finding changes a commitment in the spec or the M2 plan, record it here.)
```

- [ ] **Step 2: Commit**

```bash
git add docs/milestones/
git commit -m "docs(M1-13): M1 HIL checkpoint script"
```

---

## Task 14: CI workflow for M1 (unit + integration on push)

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install uv
        uses: astral-sh/setup-uv@v3
      - run: uv sync
      - name: API unit tests
        working-directory: apps/api
        run: uv run pytest -v
      - name: SDK unit tests
        working-directory: packages/sdk
        run: uv run pytest -v

  integration:
    runs-on: ubuntu-latest
    needs: unit
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install uv
        uses: astral-sh/setup-uv@v3
      - name: Set up pnpm
        uses: pnpm/action-setup@v4
        with:
          version: "9.12.0"
      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: pnpm
          cache-dependency-path: pnpm-lock.yaml
      - run: pnpm install --frozen-lockfile || pnpm install
      - run: uv sync --group integration
      - name: Run compose stack integration test
        run: uv run --group integration pytest tests/integration/ -v
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(M1-14): unit + integration test workflow"
```

---

## Self-Review

### Spec coverage

Mapping each M1 requirement from `docs/superpowers/specs/2026-04-23-quant-mvp-design.md` §9 M1 to the tasks that implement it:

| Spec requirement | Task(s) |
|---|---|
| Monorepo skeleton (apps/api, apps/ui, apps/accounts, packages/sdk) | T1, T2, T5, T7, T11 |
| docker-compose with Postgres + MinIO + MLflow + FastAPI + mock OIDC | T3, T4, T5, T7 |
| Alembic initialized | T6 |
| `qp up` / `qp down` / `qp doctor` | T8, T9, T10 |
| Integration: testcontainers fixture boots Postgres + MinIO + MLflow; healthchecks pass | T6 (alembic roundtrip is the testcontainers pattern), T12 (full-stack smoke) |
| E2E: `docker compose up -d && docker compose ps` all healthy within 30s | T12 (compose_up fixture uses `--wait`) |
| M1 HIL script | T13 |

All spec requirements covered. No gaps.

### Placeholder scan

Searched plan for: TBD / TODO / FIXME / XXX / "similar to" / "fill in" / "appropriate". None found. Every step shows the exact content to write.

### Type consistency

- `qp` CLI registered under `quantplatform.cli.main:app` (used consistently in T2, T8, T9, T10 and in `pyproject.toml` `[project.scripts]`)
- `quantplatform.__version__` used in T2 and referenced in T5's API (note: `api.__version__` is a separate constant by design — the API service has its own version)
- `SERVICE_ROLE` env var used in T5 (api main), T5 (Dockerfile), and the compose file (T3) — all consistent
- Ports list in `qp doctor` (T10) matches ports exposed in `docker-compose.yml` (T3): 5432, 9000, 9001, 5000, 4444, 8000, 5173
- `quantplatform.cli.up.subprocess.run` / `.down.subprocess.run` / `.doctor._check_*` — patched in tests exactly as named in implementation

No inconsistencies.

### Scope check

Plan covers one milestone (M1). Subsequent milestones (M2-M8) get their own plans after each HIL gate. This matches the spec's commitment ("No next milestone starts until prior HIL is green") and LESSONS.md's anti-mega-plan guidance.

---

## Execution notes

- Task count: 14 tasks, ~80 steps total. Budget per spec: 2 workdays.
- Commit cadence: one commit per task (14 commits).
- Test cadence: every task with an implementation step includes a failing-test-first step before code.
- Parallelization opportunities: T4 (mock OIDC), T7 (UI), T11 (accounts placeholder) are independent of each other; could be built in parallel by subagents. T3 depends on T1; T5 depends on T1; T6 depends on T5; T12 depends on T3+T4+T5+T7; T13+T14 depend on everything else.
- The pre-push hook (the full `qp e2e` story) arrives in M3+; M1 has only CI as the integration-test backstop.
