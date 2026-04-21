# apps/api — quant-platform backend

Single Docker image. At startup, the `ROLE` env var selects which role the process plays.

## Roles

| ROLE | Entry | Purpose |
| :--- | :--- | :--- |
| `api` (default) | `uvicorn app.main:app` | REST API, serves React SPA, OIDC callbacks |
| `worker-proj-ui` | `python -m app.workers.proj_ui` | Consumes `proj_ui` PGMQ queue, updates UI read-model tables |
| `worker-training` | `python -m app.workers.training` | Dispatches and polls training jobs |
| `scheduler` | `python -m app.scheduler` | APScheduler daemon emitting periodic PGMQ messages |
| `bridge-pgmq-http` | `python -m app.workers.bridge` | Drains PGMQ queues, posts to worker HTTP endpoints — enables Cloud Run request-rate autoscaling |

## Local run

```bash
cd apps/api
uv sync --all-extras
uv run uvicorn app.main:app --reload --port 8000
```

## Tests

```bash
uv run pytest -m unit        # no stack required
uv run pytest -m integration # requires docker-compose up
```
