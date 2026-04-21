# Quant Platform — Status

**Last updated:** 2026-04-21

## What exists

### Repository & CI/CD

- **GitHub repo:** <https://github.com/FreeSideNomad/quant-platform> (private, FreeSideNomad org)
- **GHCR image:** `ghcr.io/freesidenomad/quant-platform` (pushed on main)
- **Self-hosted runner:** `vm-runner-quant` registered to repo, running on `ubuntu-server.local`
  - Labels: `self-hosted,linux,x64,vm-runner,quant`
  - Container: `myoung34/github-runner:latest` (separate from LedgerTM's runner)
  - Workdir: `/srv/quant-runner/{runner-data,runner-work}` on the VM
  - Mounts Docker socket, restarts on reboot
- **GitHub Actions secrets set:** `QUANT_DB_PASSWORD`, `SESSION_JWT_SIGNING_KEY`, `BFF_TOKEN_ENCRYPTION_KEY_B64`

### Runtime architecture

Single Docker image, multiple roles:

| Role | Purpose |
| :--- | :--- |
| `api` | FastAPI REST API with Bearer JWT auth, commands + queries + models + serving routers |
| `bff` | Browser-facing reverse proxy — session cookie, CSRF, OIDC client to IdP, forwards Bearer to API |
| `idp` | Federation IdP — federates Mock/Google/Entra upstream, mints RS256 JWTs, exposes `/jwks`, `/.well-known/openid-configuration` |
| `worker-proj-ui` | UI read-model projector off PGMQ |
| `worker-training` | Picks up training jobs from PGMQ, runs LightGBM, registers in MLflow |
| `scheduler` | APScheduler daemon |

### Auth stack

- Mock OIDC seeded with `admin/admin` (roles: admin, quant, viewer) and `user/user` (roles: quant, viewer)
- BFF stores session tokens AES-256-GCM encrypted in Postgres, sets `__Host-qp_session` cookie (or `qp_session` when `BFF_SESSION_COOKIE_SECURE=false` for localhost dev)
- CSRF double-submit via `qp_csrf` readable cookie + `X-CSRF-Token` header
- PKCE, state, nonce on OIDC flow
- IdP mints our RS256 JWTs with claims: sub, iss, aud, exp, iat, jti, email, name, roles, tenant_id, upstream_idp, upstream_sub, typ
- API verifies via IdP's `/jwks` with kid-based rotation-aware re-fetch
- Role-based guards: `requires_role("admin", "quant", ...)`

### Data platform

- Bronze: MinIO (dev) / GCS (prod) — not yet exercised; synthetic path writes silver directly
- Silver: `daily_prices_silver` — bi-temporal `knowable_at` + `source_uri`
- Gold: `features_gold` — Alpha-style momentum/vol/volume features + forward 1-day return target, `knowable_at` backdated to trade_date EOD

### ML pipeline (Qlib-inspired)

- Synthetic OHLCV generator (deterministic, 5 instruments × ~2y)
- Feature set: `mom_5`, `mom_20`, `vol_20`, `return_mean_20`, `hl_range`, `vol_ratio_20`
- Training: LightGBM with time-ordered train/val split, early stopping, MLflow experiment tracking
- Model registry: MLflow 3.1 via the `register_model` path (model version `qlib-lgbm/1`)
- Inference: `/api/serving/qlib-lgbm/predict` with feature hash + latency_ms + inference_log audit row

### Frontend

React 19 + Vite + TanStack Router + Tailwind v4 + Radix + Motion + Zustand + Sonner. Design tokens verbatim from `doodle-1`.

Routes:
- `/` — Overview with live health, ping CQRS flow demo
- `/models` — registered models list
- `/models/:modelId` — model detail with training runs, inference form, inference log

### Tests

- **22 Python tests** (unit + integration): auth deps, BFF cookies, IdP tokens, config, health, full BFF→IdP→Mock auth flow, full ML training → inference round-trip
- **7 frontend tests**: AppShell rendering, auth state, API client with CSRF + 401 redirect
- **All green** as of last local run

## How to run locally

```bash
make setup     # install uv + pnpm deps
make dev       # docker-compose --profile local up
make migrate   # alembic upgrade head against local postgres
# optional: seed a model row
docker compose --profile local exec -T postgres psql -U quant -d quant -c \
  "INSERT INTO models(id, name, description, algorithm, owner_email) \
   VALUES ('qlib-lgbm', 'qlib-lgbm', 'Alpha-style LGBM demo', 'lightgbm', 'admin@example.test') \
   ON CONFLICT (id) DO NOTHING;"
# then visit:
#   http://localhost:8080     (BFF — redirects to login)
#   http://localhost:9800     (mock IdP for troubleshooting)
#   http://localhost:5000     (MLflow UI)
#   http://localhost:9001     (MinIO console — minioadmin/minioadmin)
#   http://localhost:5173     (Vite dev server if you run `pnpm --filter web dev`)
```

Log in as `admin/admin`. Submit a training run from the Models page. Run inference.

## What's not yet done

- **VM-facing deploy workflow end-to-end test** — the workflow exists and points at the quant runner; not yet triggered with a real image pull (awaits the `Publish image` workflow on main to complete and then `workflow_run` → deploy)
- **Real Qlib data ingestion** — the bronze loader currently synthesises OHLCV. Swapping to Qlib's `GetData().qlib_data(...)` is one function call; bronze→silver contract stays the same.
- **GPU training path** — wiring exists (`compute_profile=local-gpu` / `cloud-gpu`) but dispatchers to Vertex AI / local GPU not implemented (explicit error returned).
- **Control plane** — fleet management application not started.
- **Terraform** — per-tenant GCP module not started.

## Environments

| | Local (Mac) | Dev VM (ubuntu-server.local) | Prod (GCP) |
| :--- | :--- | :--- | :--- |
| Postgres | docker-compose w/ PGMQ image | TBD (could reuse infra-postgres or dedicated) | Cloud SQL / AlloyDB per tenant |
| MLflow | docker-compose, v3.1, Postgres-backed | TBD | Cloud Run per tenant |
| Runner | n/a | `vm-runner-quant` (live) | GitHub-hosted + WIF |
| Cookies | `qp_session` (no Secure) | `qp_session` (no Secure) | `__Host-qp_session` (Secure) |
