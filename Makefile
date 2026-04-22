SHELL := /bin/bash

API_DIR := apps/api
WEB_DIR := apps/web

.PHONY: help setup dev dev-stop migrate seed demo-fresh run test test-unit test-int test-e2e lint format clean logs

help:
	@echo "Targets:"
	@echo "  setup       Install Python (uv) and Node (pnpm) dependencies"
	@echo "  dev         Bring up docker-compose stack (postgres, minio, mlflow, mock-oidc)"
	@echo "  dev-stop    Stop docker-compose stack"
	@echo "  migrate     Apply Alembic migrations against local Postgres"
	@echo "  seed        Seed sample tenant, users, and fixtures"
	@echo "  run         Run the API role locally with hot reload"
	@echo "  test        Run unit + integration tests"
	@echo "  test-unit   Run unit tests only (no stack required)"
	@echo "  test-int    Run integration tests against docker-compose"
	@echo "  test-e2e    Run Playwright end-to-end tests"
	@echo "  lint        Ruff + pyright + frontend linters"
	@echo "  format      Auto-format Python and TypeScript"
	@echo "  logs        Tail docker-compose logs"
	@echo "  clean       Stop stack and remove volumes"

setup:
	cd $(API_DIR) && uv sync --all-extras
	pnpm install

dev:
	docker compose up -d
	@echo "Stack up. Postgres @ localhost:5433, MinIO @ :9000, MLflow @ :5000, Mock OIDC @ :9800"

dev-stop:
	docker compose down

migrate:
	cd $(API_DIR) && uv run alembic upgrade head

seed:
	cd $(API_DIR) && uv run python -m app.scripts.seed

demo-fresh: dev migrate
	cd $(API_DIR) && uv run python -m app.scripts.demo_seed
	@echo "Demo seeded. API: http://localhost:8000/api/queries/pings"
	@echo "Dagster lineage: http://localhost:3000"

run:
	cd $(API_DIR) && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test-unit:
	cd $(API_DIR) && uv run pytest -m unit -q

test-int: dev
	cd $(API_DIR) && uv run pytest -m integration -q

test: test-unit test-int

test-e2e:
	pnpm --filter web test:e2e

lint:
	cd $(API_DIR) && uv run ruff check . && uv run pyright
	pnpm --filter web typecheck

format:
	cd $(API_DIR) && uv run ruff format .
	pnpm --filter web exec prettier --write src

logs:
	docker compose logs -f --tail=200

clean:
	docker compose down -v
	rm -rf $(API_DIR)/.pytest_cache $(API_DIR)/.ruff_cache $(API_DIR)/.mypy_cache
	rm -rf $(WEB_DIR)/dist $(WEB_DIR)/node_modules/.cache
