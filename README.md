# Quant Platform

An open-source-first, silo-tenant productionalization platform that lets a quant ship a model from notebook to audited production without an engineering hand-off.

**Status:** MVP-B in design. The previous attempt (MVP-A) was parked on 2026-04-22 after an architectural retrospective; see [`LESSONS.md`](./LESSONS.md). MVP-B is a greenfield build on the pre-MVP-A baseline, shaped around one developer journey (the quant) and gated by 8 human-in-the-loop milestones.

Current MVP design: [`docs/superpowers/specs/2026-04-23-quant-mvp-design.md`](./docs/superpowers/specs/2026-04-23-quant-mvp-design.md).

## Quick start (planned)

Once the MVP ships, onboarding is:

```bash
# Install the qp CLI (macOS or Linux)
curl -sSfL https://get.quantplatform.io | sh
# or
uv tool install quantplatform

# Scaffold a strategy and run it locally
qp new strategy hello-world
cd hello-world
qp up                    # start the full stack in docker-compose
qp run hello-world       # train + walk-forward + PBO/DSR/CPCV gate
```

Open <http://localhost:5173> to view the walk-forward report and promote the model. Everything runs on your laptop — Postgres, MinIO, MLflow, FastAPI, worker, UI, mock OIDC — via one docker-compose stack.

None of this is built yet. The spec defines what will be true when MVP-B is complete.

## Architecture at a glance

- **Single Docker image, multiple roles** — one image deployed as API / training worker / serving worker, role selected at runtime
- **Orchestration** — PGMQ (Postgres queue) + APScheduler + worker; no Dagster
- **Model registry** — MLflow 2.16+ with Aliases (never Stages); pyfunc packaging for research-to-production parity
- **Honesty substrate** — PBO, DSR, CPCV, walk-forward are enforced gates that block promotion of overfit backtests
- **Data lineage** — content-hashed reads via the SDK; bi-temporal `_knowable_at` / `_valid_from` / `_valid_to` columns; hash-chained audit log
- **Frontend** — React 19 + Vite + TanStack Router + Tailwind v4 + Radix + Motion + Zustand (doodle-1 stack)
- **Developer surface** — a single `qp` CLI (six commands in MVP) + project-per-strategy Python packages; no codegen

The architecture assumes a hedge-fund customer will eventually run each tenant in their own GCP project under the Bring-Your-Own-Cloud model. The MVP is the laptop-side of that topology; the deployed tenant is the same Docker image with different env vars.

## Repository structure (planned, per spec)

```
quant-platform/
├── apps/
│   ├── api/             # FastAPI platform services (single image; api + worker roles)
│   ├── ui/              # React / Vite / TanStack frontend
│   └── accounts/        # FastAPI accounts service (hosted at accounts.quantplatform.io)
├── packages/
│   └── sdk/             # quantplatform Python package (SDK + qp CLI)
├── templates/
│   ├── hello-world/     # volatility-forecast scaffold (passes gate)
│   └── hello-world-returns/  # returns-forecast scaffold (fails gate; teaching)
├── docs/
│   └── superpowers/
│       ├── specs/       # brainstorming outputs
│       ├── plans/       # implementation plans (writing-plans skill)
│       └── milestones/  # M1-M8 HIL checkpoint docs
├── blueprint/           # reference architecture (broad; the spec is the MVP cut)
├── docker-compose.yml
├── docker-compose.debug.yml
├── LESSONS.md           # MVP-A retrospective
├── START.md             # kickoff brief for the MVP-B session
└── README.md
```

## Documentation

- [`LESSONS.md`](./LESSONS.md) — MVP-A retrospective; the failure modes MVP-B avoids
- [`START.md`](./START.md) — kickoff brief; three pillars for MVP-B
- [`docs/superpowers/specs/2026-04-23-quant-mvp-design.md`](./docs/superpowers/specs/2026-04-23-quant-mvp-design.md) — current MVP design
- [`blueprint/`](./blueprint/) — reference architecture (v1-scope; the MVP is a narrower cut)

## Deployment topology

- **Laptop (MVP default)** — one `docker compose up` brings the entire stack. This is where the quant lives. Free.
- **Deployed tenant (post-MVP, future)** — per-customer GCP project, provisioned by Terraform, same Docker image, Cloud Run + Cloud SQL + GCS. Paid.

The MVP does not exercise the deployed tenant path. The control-plane provisioner, Terraform modules, and deploy pipeline are all future work.

## Development targets

- **`ubuntu-server` (192.168.2.150)** — hosts side-services (`accounts.quantplatform.io` for the open-core funnel) via Docker + Cloudflare Tunnel
- **`windows` (192.168.2.250)** — Windows Docker host; self-hosted GitHub Actions runner; dev/staging target for the platform itself
