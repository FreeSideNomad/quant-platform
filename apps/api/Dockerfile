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
COPY migrations ./migrations
COPY alembic.ini ./
# Bundled dataset metadata (aapl_daily.meta.json) is read by the v1
# migration at upgrade time. The parquet itself is uploaded to MinIO by
# the minio-init service via bind-mount in docker-compose.yml; the api
# image only needs the small sidecar JSON for the migration to register
# content_hash + schema_json.
COPY data ./data

# Install deps
RUN uv pip install --system --no-cache .

# worker_training role needs debugpy for remote attach
RUN pip install --no-cache-dir debugpy==1.8.16

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
