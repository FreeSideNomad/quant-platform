# Quant Platform

Reference implementation of the Quant Platform Blueprint. A single Docker image, multiple roles, deployed to the dev VM via a self-hosted GitHub Actions runner.

## Quick start (local, Mac)

```bash
make setup      # install Python + Node dependencies, pull images
make dev        # bring up docker-compose stack (postgres, minio, mlflow, mock-oidc)
make migrate    # apply Alembic migrations
make seed       # seed tenants, users, sample data
make run        # start the API role locally with hot reload
```

Open <http://localhost:8000/health> to verify.

## Repository shape

```
quant-platform/
├── apps/
│   ├── api/          # Python FastAPI + workers (single image source)
│   └── web/          # React 19 + Vite + TanStack Router frontend
├── compose/          # docker-compose service configs (mock OIDC, postgres init, caddy)
├── migrations/       # Alembic schema versions (under apps/api/migrations)
├── scripts/          # Developer and ops scripts
├── .github/workflows # PR checks + deploy workflows
├── docker-compose.yml
├── Makefile
├── package.json      # pnpm workspace root
├── pnpm-workspace.yaml
└── .env.example
```

## Deployment targets

- **Local (Mac)** — docker-compose brings up every service on the laptop. Golden rule: nothing in production has no local equivalent.
- **Dev VM** (`ubuntu-server.local`, 192.168.2.100) — self-hosted GitHub runner pulls images from `ghcr.io/freesidenomad/quant-platform:<tag>` and runs `docker compose up` on the VM's Docker engine. The VM's existing `infra-postgres` is reused for persistence; no separate Postgres for the quant platform in this environment.
- **Production GCP** (future) — per-tenant Cloud Run services stamped from the same image, Cloud SQL per tenant, blue/green via revisions.

See `blueprint/` (sibling directory) for full architecture documentation.
