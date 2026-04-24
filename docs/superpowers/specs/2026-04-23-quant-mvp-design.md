---
title: Quant Platform MVP — Design Spec
date: 2026-04-23
status: draft (awaiting user review)
session: brainstorming follow-up to MVP-A park (2026-04-22)
scope: MVP for the quant productionalization platform, journey A (quant-as-developer)
supersedes: none (greenfield on pre-MVP-A baseline at commit a9f902c)
reference artefacts:
  - LESSONS.md (MVP-A retrospective; 2026-04-22)
  - START.md (this session's kickoff brief; 2026-04-22)
  - blueprint/ (reference architecture; 2026-04-21)
  - memory/MEMORY.md (carry-over context)
---

# Quant Platform MVP — Design Spec

## 1. Context

The previous attempt, MVP-A (2026-04-21 → 2026-04-22), shipped 23 tasks and 38 commits in ~24 hours with 114 passing tests — and was architecturally wrong. Its principal failure was "add Dagster everywhere" made mid-build, which compounded into a per-strategy codegen pattern (RCE-shaped via `_slugify()`), bronze-cache hacks, MLflow Aliases/Stages drift, and scope inflation from "demoable MVP" to "MVP + Dagster everywhere + walk-forward gates + medallion architecture + reverse-proxied orchestration UI." MVP-A is archived on GitHub (`archive/mvp-a-rushed-2026-04-22` branch + `archive-mvp-a-2026-04-22` tag) and locally at `../deployment/quant-platform-archive-2026-04/`. Full retrospective: `LESSONS.md`.

This spec describes MVP-B: a greenfield build on the pre-MVP-A baseline (`a9f902c`), shaped around one developer journey (the quant writing a strategy), tested through milestones with human-in-the-loop checkpoints, and explicitly reverting MVP-A's core architectural mistake.

## 2. Grand vision (recap)

Single-sentence pitch, inherited from `blueprint/positioning/`:

> An open-source-first, silo-tenant productionalization platform that lets a quant ship a model from notebook to audited production without an engineering hand-off, and lets their fund pass an LP's operational due-diligence questionnaire from screenshots in the UI.

Three load-bearing differentiators:
1. **Silo + BYOC by default** — dedicated GCP project per tenant; customer data and code never leave their cloud perimeter.
2. **Open-source-first stack** — every load-bearing component is OSS; customers can self-host.
3. **Quant-native, not generic-ML** — PBO, DSR, CPCV, walk-forward, bi-temporal data, hash-chained audit log are platform *defaults* that gate promotion, not configurable add-ons.

MVP scope for this session: the minimum build that exercises all three differentiators through one journey (journey A, the quant), on a laptop, under the golden rule (everything runs locally via docker-compose).

## 3. Scope of this MVP (Approach 2 — "Demo-complete MVP")

Out of three alternatives considered (Lean = SDK-only no UI, Demo-complete = this spec, Wide = adds AI assist + BYO-data + cross-sectional example), **Approach 2** is selected: it exercises all three pillars of START.md (SDK, hello-world model, clickable UI) without recreating the scope-inflation failure mode of MVP-A.

### 3.1 In scope

**Single journey (journey A, the quant):**

1. Install `qp` CLI on a laptop
2. `qp auth login` (optional; unlocks telemetry and the hosted-tenant funnel)
3. `qp new strategy hello-world` — scaffold a volatility-forecasting strategy
4. `qp up` — start the local stack via docker-compose
5. `qp run hello-world` — train + walk-forward + PBO/DSR/CPCV gate; passes
6. Open `localhost:5173`, view the walk-forward report, click Promote
7. Trigger an inference from the UI, see the prediction
8. Drill from the inference back to the model version, the training run, and the input datasets
9. Also available: `qp new strategy hello-world-returns` — companion template that demonstrably fails the gate, teaching users the promotion is real

**Three pillars of START.md delivered:**

- **SDK v0** — `quantplatform` Python package; `Strategy` contract; `sdk.data.*` as the enforcement boundary for data lineage; pyfunc model packaging for research-to-production parity.
- **Hello-world quant model** — HAR-style realized-variance forecast on bundled SPY daily OHLCV (10 years, ~30 KB Parquet); companion returns-prediction template that fails the gate.
- **Clickable UI prototype** — React 19 + Vite + TanStack Router + Tailwind v4 + Radix + Motion + Zustand + Sonner + Geist (doodle-1 stack); beats 1–9 above all navigable.

### 3.2 Explicitly out of scope (for this MVP)

Deferred to future specs / v2:

- **Journey B** (platform engineer onboarding) and **Journey C** (LP / compliance viewer) — both captured as future-feature specs.
- `qp ai <prompt>` — Claude Agent SDK integration (`qp ai explain run`, `qp ai suggest-threshold`, `qp ai new-strategy`).
- `qp data register <name>` — bring-your-own-data registration flow. MVP uses bundled data only.
- `qp deploy` — push to tenant GCP project. The image is built by CI, but the deploy path is not exercised in MVP.
- `qp submit` — scheduled / background runs via PGMQ. MVP uses interactive `qp run` only.
- `qp watch` — file-watch hot reload.
- `qp promote` as CLI — promotion is UI-only for MVP (CLI gets the verb in v2).
- Homebrew tap — MVP ships via `uv tool install` and `curl | sh`; tap is polish.
- Bi-temporal silver-layer ingestion pipelines — the `_knowable_at` / `_valid_from` / `_valid_to` column scheme is supported in the data model, but ingestion tooling is v2.
- Multi-instrument / cross-sectional example.
- Dagster, in any form.

## 4. Architecture decisions (recorded)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Orchestration | PGMQ + APScheduler + worker | LESSONS.md §core mistake: Dagster tripled failure surface for zero demoable benefit. None of the four "earns-its-keep" conditions apply at MVP scale. |
| 2 | Topology | 100% local docker-compose for dev; GCP tenant mode for deployed prod; **no hybrid / agent / remote control plane**. | Matches golden rule; same image + env-var swap between modes. |
| 3 | CLI language | Python | Same package as SDK (single wheel, two entrypoints); Claude Agent SDK is Python-native; business model doesn't depend on client-side enforcement, so Rust tamper-resistance has no benefit. |
| 4 | Strategy loading | Project-as-Python-package, host-run for dev, container-run for pre-push e2e | Closes the MVP-A codegen hole (no code-on-disk from user input). Best debug UX (native IDE). Pre-push container run closes drift. |
| 5 | Data lineage | Platform-owned content hashing + bi-temporal columns; NOT DVC / git-lfs / LakeFS | Bi-temporal point-in-time is the dominant quant concern; content hashing + Postgres lineage table handles reproducibility without external tools. |
| 6 | Model registry | MLflow 2.16+ with Aliases only; `.stage` accessor banned via `qp check` AST walk | MVP-A's Aliases/Stages drift failure must not recur; CI-enforced. |
| 7 | Model packaging | MLflow `pyfunc` wrapping training-time feature code | Research-to-production parity by construction; eliminates train-serve skew as a class. |
| 8 | Single image, multi-role | One Docker image; role (`api` / `worker` / `serving`) selected at runtime via env var | Blueprint bet #3; preserved verbatim. |
| 9 | Auth | BFF + mock OIDC for local UI; GitHub OAuth device flow for `qp auth login` (hosted accounts service) | Local: no friction. Hosted: zero-infra device flow. |
| 10 | Accounts service hosting | FastAPI on `ubuntu-server` (192.168.2.150) via Cloudflare Tunnel at `accounts.quantplatform.io` | Free, on-brand with open-core, migration to GCP only when scale or SLAs demand. |
| 11 | Frontend stack | React 19 + Vite + TanStack Router + Tailwind v4 + Radix + Motion + Zustand + Sonner + Geist (doodle-1) | Explicit commitment; matches positioning reference. |
| 12 | Validation math | Port PBO, DSR, CPCV, walk-forward harness from `../deployment/quant-platform-archive-2026-04/app/quant/validation/` | LESSONS.md §worth-keeping. Math is sound; was not Dagster-coupled. |
| 13 | Audit log | Hash-chained with `pg_advisory_xact_lock(0xA7D17_106)` pattern ported from MVP-A | LESSONS.md §worth-keeping. Survived concurrent-writer race conditions. |
| 14 | Promotion mechanics | CQRS: UI Promote button → command → validate gate → emit `ModelPromoted` event → MLflow alias flip + serving lazy-reload | Closes MVP-A's "code lied about the spec for 20 commits" failure; audit-first by design. |
| 15 | Testing | Five layers: unit, integration (testcontainers), E2E (`qp e2e`), UI (Playwright), HIL (human-scripted) | MVP-A had rigorous TDD at wrong level; HIL is the missing layer. |
| 16 | Milestones | 8 gated milestones with HIL checkpoint ending each; no next milestone starts until prior HIL is green | MVP-A had no user feedback loop during execution; this closes that. |

## 5. System architecture

### 5.1 Local topology (MVP demo, `qp up` on laptop)

```
┌─ Host (quant's laptop) ────────────────────────────────────────────────┐
│  qp CLI (`~/.local/bin/qp` via uv tool install)                        │
│  Python venv for the strategy project (uv-managed, per-project)        │
│  Strategy code runs here by default: `qp run hello-world`              │
│  IDE (VS Code / PyCharm) with scaffolded debug configs                 │
│                                                                        │
│          │ HTTP                                                        │
│          ▼                                                             │
└────────────────────────────────────────────────────────────────────────┘
┌─ docker-compose network (`qp up`) ─────────────────────────────────────┐
│                                                                        │
│   ┌───────────────┐   ┌─────────────┐   ┌─────────────────────────┐    │
│   │ FastAPI :8000 │   │ UI    :5173 │   │ mock OIDC       :4444   │    │
│   │ (platform API)│   │ (Vite)      │   │ (for local UI session)  │    │
│   └───────┬───────┘   └──────┬──────┘   └─────────────────────────┘    │
│           │                  │                                         │
│           ▼                  │                                         │
│   ┌───────────────────────────┴─────────────────────────────────┐      │
│   │ Postgres :5432                                              │      │
│   │   strategies, runs, events (hash-chained audit),            │      │
│   │   lineage_reads, datasets, dataset_versions,                │      │
│   │   mlflow.*, pgmq.queue, silver/gold bi-temporal tables      │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                                                                        │
│   ┌───────────────┐   ┌──────────────────────────────────────────┐     │
│   │ MinIO  :9000  │   │ MLflow server :5000                      │     │
│   │ (S3 API,      │◄──┤ (uses Postgres + MinIO under the hood)   │     │
│   │  artifacts)   │   │                                          │     │
│   └───────────────┘   └──────────────────────────────────────────┘     │
│                                                                        │
│   ┌──────────────────────────────────────────────────────────────┐     │
│   │ Worker container (same image, WORKER_ROLE=serving for MVP)   │     │
│   │   Lazy-reloads pyfunc models on `ModelPromoted` event        │     │
│   │   Handles POST /serving/<model>/predict                      │     │
│   │   (Also handles WORKER_ROLE=training for `qp e2e` container  │     │
│   │    mode and pre-push; not used by default `qp run`.)         │     │
│   └──────────────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────────────────┘
                          │
                          │ (only when `qp auth login` or telemetry flows)
                          ▼
┌─ `accounts.quantplatform.io` (ubuntu-server 192.168.2.150) ────────────┐
│  FastAPI `accounts-api` container                                      │
│  GitHub OAuth device flow, /me, /events                                │
│  Postgres (shared instance, schema `accounts`)                         │
│  Exposed via Cloudflare Tunnel                                         │
└────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Where strategy code executes

- **Default `qp run`**: strategy runs as a subprocess on the host, in the project's uv venv. Native IDE debugging. Zero container round-trip.
- **`qp run --container` or `qp e2e`**: strategy runs inside the worker container (WORKER_ROLE=training), with the project bind-mounted at `/workspace`. `debugpy` listening on `:5678` for remote attach. Used for drift-catching and pre-push gates.
- **Deployed prod (post-MVP)**: strategy ships as an installed Python package inside the tenant's worker image; runs via Cloud Run Jobs. Same code path.

### 5.3 Why "worker mostly idle" at MVP

Acknowledged tradeoff: the worker container in MVP mostly serves inference (the PGMQ+worker orchestration pattern is provisioned but not heavily exercised). The seat is built for future `qp submit`, scheduled runs, and training-in-worker when a user opts in via `--container`. MVP deliberately under-uses it rather than over-engineering it. This is a conscious, recorded decision — not an oversight.

## 6. Components

### 6.1 `quantplatform` Python package (SDK + CLI)

Single PyPI wheel. Two entry points:
- `import quantplatform` — the SDK
- `qp` — the CLI (exposed via `[project.scripts]`)

Installation paths:
- `uv tool install quantplatform` (Python-native)
- `curl -sSfL https://get.quantplatform.io | sh` (ensures uv then `uv tool install`)
- Homebrew tap deferred to v2

#### 6.1.1 SDK surface (v0)

```python
from quantplatform import Strategy, data, validation

class VolHAR(Strategy):
    name = "vol-har"
    thresholds = {"pbo_max": 0.5, "dsr_min": 0.0}

    def features(self, df):
        # HAR-style: 1d, 5d, 22d realized variance features
        return df.with_columns([...])

    def model(self):
        return lightgbm.LGBMRegressor(...)

    def target(self, df):
        # next-day realized variance
        return df["rv_1d"].shift(-1)

def main():
    df = data.ohlcv(ticker="SPY", as_of=run.as_of)
    strategy = VolHAR()
    strategy.train_and_validate(df)
```

Key SDK guarantees:
- `data.ohlcv(...)` / `data.get(...)` are the ONLY sanctioned data access paths; direct `pl.read_*` / `pd.read_*` / `open()` / `requests.get()` in strategy code are flagged by `qp check`.
- Every `data.*` call writes a row to `lineage_reads` with `(run_id, dataset_version_id, as_of, filter_predicates, content_hash, read_timestamp, rows_returned)`.
- `Strategy.train_and_validate(df)` runs walk-forward + PBO + DSR + CPCV and emits a `GateEvaluated` event; on pass, registers the pyfunc-wrapped model in MLflow.
- Thresholds for the gate are declared on the Strategy class and are the *only* source of truth; the platform reads them on promote.

Ergonomic target: hello-world under 40 lines of user-written code. Benchmarked against Modal's decorator style — ours must not be wordier.

#### 6.1.2 CLI surface (MVP = 6 commands)

| Command | Purpose |
|---|---|
| `qp auth login` | GitHub device flow; stores `~/.qp/credentials`; one-time telemetry opt-in prompt |
| `qp new strategy <name>` | Scaffold a project from template (V by default; R via `--template returns`) |
| `qp up` | Start the local stack (wraps `docker compose up -d`) |
| `qp down` | Stop the local stack |
| `qp doctor` | Verify Docker, uv, Python version, free ports, project-venv health |
| `qp run <strategy>` | Execute strategy (host by default; `--container` for container-run; `--debug` to wait for IDE attach) |

Deferred verbs (post-MVP): `qp e2e` (used internally by pre-push hook but not a public verb in MVP), `qp promote`, `qp logs`, `qp test`, `qp check`, `qp ai`, `qp data register`, `qp watch`, `qp submit`, `qp deploy`.

**`qp check`** is used internally during `qp new` scaffolding and in pre-commit to AST-walk strategies, but is not exposed as a public command in MVP CLI surface. ruff and pyright remain user-invoked via `uv run`.

#### 6.1.3 Scaffolded project structure

```
hello-world/
├── src/vol_har/
│   ├── __init__.py
│   └── strategy.py                    # the user's code
├── data/spy_daily.parquet             # bundled 10-year SPY OHLCV (~30 KB)
├── tests/
│   ├── test_strategy.py               # scaffold tests
│   └── conftest.py
├── qp.toml                            # name, entry, thresholds, data deps
├── pyproject.toml                     # deps pinned via uv.lock
├── uv.lock
├── .vscode/
│   ├── launch.json                    # "Debug strategy (host)" + "(container)"
│   ├── settings.json
│   ├── tasks.json
│   └── extensions.json
├── .idea/runConfigurations/
│   ├── Debug_host.xml                 # PyCharm Community + Professional
│   └── Debug_container.xml
├── .devcontainer/devcontainer.json    # optional: full remote-IDE mode
├── .pre-commit-config.yaml            # ruff + pyright + qp-check + unit tests
├── .githooks/pre-push                 # qp e2e (container build + run)
└── README.md                          # how to debug, how to run, how to promote
```

### 6.2 Platform services (single Docker image, multi-role)

One Python image built from `apps/api`. Role selected at startup via `SERVICE_ROLE` env var.

- **`SERVICE_ROLE=api`** — FastAPI, mounted at `:8000`. Handles HTTP requests from CLI, UI, and strategies. Writes to Postgres, publishes to PGMQ, talks to MLflow.
- **`SERVICE_ROLE=worker_serving`** — Subscribes to `ModelPromoted` events via PGMQ. Loads pyfunc models from MLflow. Serves `POST /serving/<model>/predict` (proxied through the API).
- **`SERVICE_ROLE=worker_training`** — Used only for `qp run --container` and `qp e2e`; reads from PGMQ training queue and executes strategy code with bind-mounted project at `/workspace`.

Application schema in Postgres (abbreviated):

- `strategies` — name, owner, thresholds, git_sha, created_at
- `runs` — run_id, strategy_id, as_of, status, git_sha, uv_lock_hash, started_at, finished_at
- `events` — hash-chained audit (`pg_advisory_xact_lock`), event_type, payload, prev_hash, this_hash
- `datasets` — name, description, schema_json, content_hash_scheme
- `dataset_versions` — dataset_id, version_tag, storage_uri, content_hash, schema, effective_at
- `lineage_reads` — run_id, dataset_version_id, as_of, filter_predicates, content_hash, read_timestamp, rows_returned
- `inference_log` — inference_id, model_version_id, features_hash, prediction, latency_ms, requested_at
- `pgmq.training_jobs`, `pgmq.model_promotions` — work queues

Alembic manages migrations. `testcontainers` exercises migration roundtrip (`alembic downgrade base && alembic upgrade head`) — pattern ported from MVP-A.

### 6.3 UI (`apps/ui`)

React 19 + Vite + TanStack Router + Tailwind v4 + Radix + Motion + Zustand + Sonner + Geist.

Screens (MVP):

1. **Login** — mock OIDC in local mode; session cookie writeable by `qp up --open-browser`
2. **Strategies list** — cards of registered strategies, last-run status
3. **Runs list** — per strategy, sortable by gate outcome
4. **Run detail** — walk-forward fold-by-fold chart (per-fold metric over time), PBO / DSR / CPCV values with tooltips explaining each, gate verdict banner, per-fold metrics table, artifact links (SHAP plot, fold predictions)
5. **Promote dialog** — modal with gate-status-aware copy; refuses promotion for failed runs with clear error
6. **Inference form** — feature inputs → POST to serving → prediction displayed; stores to inference_log
7. **Drill-back** — inference row → model version → training run → dataset versions → strategy git SHA; each hop is a link

Visual discipline: no "SOTA" language, no placeholder text that contradicts reality, no chart that implies data we don't have. Copy is terse and literal.

### 6.4 Accounts service (`apps/accounts`)

FastAPI application, containerized, deployed to `ubuntu-server` (192.168.2.150) via Docker, exposed as `accounts.quantplatform.io` through Cloudflare Tunnel.

Routes:
- `POST /device/code` — initiate GitHub device flow
- `GET /device/token` — poll for GitHub token
- `GET /me` — authenticated profile
- `POST /events` — telemetry ingest (anonymous command, duration, success, qp version; never arguments, never strategy code, never data)

Opt-out: `QP_TELEMETRY=0` env var, `DO_NOT_TRACK=1` env var, or `qp auth logout`.

Storage: shares Postgres instance on ubuntu-server with other personal-project schemas; owns schema `accounts`.

## 7. Key mechanisms

### 7.1 Content-hashed data lineage

Every `sdk.data.*` call:
1. Resolves dataset + version → `storage_uri` (Parquet in MinIO)
2. Computes / reads cached content hash of the underlying bytes
3. Applies `_knowable_at <= as_of` bi-temporal filter (future, when silver layer exists)
4. Writes `lineage_reads` row inside a transaction that also advances the audit log hash-chain
5. Returns the Polars DataFrame

Reproducibility: given `(git_sha, uv_lock_hash, lineage_reads[*].content_hash)`, a re-run produces byte-identical inputs (up to explicit RNG seeds, which are also pinned on `runs`).

### 7.2 Hash-chained audit log

Ported from MVP-A (`pg_advisory_xact_lock(0xA7D17_106)` pattern). Every event insert acquires the advisory lock, reads the previous hash, computes `this_hash = sha256(prev_hash || canonical_json(event))`, inserts atomically. Integrity property-tested with `hypothesis` under simulated concurrent writes.

### 7.3 PBO / DSR / CPCV promotion gate

Ported from MVP-A's `app/quant/validation/`. Pure functions; 100% line coverage; tested against López de Prado reference examples.

Gate logic:
- Walk-forward produces a sequence of out-of-sample performance observations
- PBO (Probability of Backtest Overfitting) is computed per Bailey & López de Prado 2014
- DSR (Deflated Sharpe Ratio) accounts for selection bias
- CPCV (Combinatorial Purged Cross-Validation) is the cross-validation method, not k-fold

Gate passes iff `PBO <= threshold_pbo_max AND DSR >= threshold_dsr_min`. Thresholds declared on the `Strategy` class, read by the platform at promote time, recorded on `runs` and on the `GateEvaluated` event.

### 7.4 Alias-based promotion (no Stages, ever)

- MLflow pinned `>= 2.16`
- Promotion path: UI Promote button → `POST /models/<name>/versions/<v>/promote` → command handler validates gate verdict on `runs.gate_passed` → emits `PromotionRequested` → validator → `ModelPromoted` event → `MlflowClient().set_registered_model_alias(name, "production", v)` → serving worker lazy-reloads
- Failure mode: gate-failed runs cannot be promoted; command handler refuses and UI/CLI displays the blocking reason
- `qp check` AST-walk bans `.stage` / `transition_model_version_stage` across the entire codebase

### 7.5 `pyfunc` research-to-production parity

Feature computation and model inference are both defined in the Strategy class. `train_and_validate()` serializes the trained pipeline (features + model) as an MLflow `pyfunc`. Serving loads the same pyfunc and calls `predict()` with the same feature-computation code. By construction, train-serve skew is impossible for platform-resident code paths.

### 7.6 Strategy as Python package (no codegen)

Strategies are Python packages in the user's project directory. `qp new strategy` scaffolds. `qp up` bind-mounts the project into the worker container (for container mode) or leaves it alone (for host mode).

Registration flow (no user-called `register()` function; the platform handles it):
1. `qp run <name>` reads `qp.toml` for `name`, `entry`, and thresholds
2. Before executing, the CLI imports the Strategy class (via the declared entry point) and confirms `Strategy.name` matches `qp.toml`
3. The CLI POSTs a "strategy upsert" to the API with `(name, entry_point, thresholds, git_sha, uv_lock_hash)`; the API either inserts a new `strategies` row or updates metadata on an existing row
4. The API returns a `strategy_id`; the CLI creates the `runs` row referencing it, then kicks off execution

No user code is moved by the platform. The user's Python package is the source of truth; `strategies` rows are metadata pointers. The Strategy class is imported in-process by the same Python that executes `train_and_validate` — no separate "build" or "deploy" phase for MVP.

### 7.7 Host-run + container-e2e debug story

Dev-loop default: strategy runs in the host's uv venv. Native IDE debugging works. Iteration is ~2 seconds.

Drift-catching: pre-push hook runs `qp e2e` — builds the worker image, runs the strategy inside the container with `debugpy` optionally available, asserts same-outcome. Budget: <90 seconds with BuildKit layer cache.

Both paths exercise the same Python code and the same platform services.

## 8. Testing strategy

Five layers. Each layer has a speed budget and a run-timing.

| Layer | Catches | Tool | Budget | When |
|---|---|---|---|---|
| Unit | Logic errors in pure functions | pytest, mocks, hypothesis | <30s total | Every save; pre-commit |
| Integration | Wiring errors with real services | pytest + testcontainers | <3min total | Pre-commit (optional); pre-push (required) |
| E2E (`qp e2e`) | Host↔container drift; image-build correctness | docker build + container strategy run | <90s | Pre-push (required); CI main |
| UI | Frontend happy paths + regressions | Playwright | <2min | Every UI commit; CI main |
| HIL | UX friction, visual defects, spec gaps | Scripted manual walkthrough | 15–60min | End of every milestone |

Absolute coverage requirements (not percentages — absolutes):

- Every public SDK method: ≥1 unit test
- Every API endpoint: ≥1 integration test
- Every UI screen: ≥1 Playwright happy-path test
- PBO/DSR/CPCV math: 100% line coverage
- Audit hash-chain: property tests under simulated concurrency
- `hello-world` E2E: always-green sentinel in pre-push and CI

## 9. Milestones

Eight gated milestones. Each ends with an HIL checkpoint that must sign off before the next milestone begins. Failure to pass HIL is the system working correctly — it surfaces a defect or a spec gap for correction before sunk cost compounds.

### M1 — Skeleton + infrastructure (target: 2 workdays)

**Deliverable:** Monorepo skeleton; docker-compose with Postgres + MinIO + MLflow + FastAPI placeholder + mock OIDC; Alembic initialized; `qp up` works.

**Automated tests:**
- Integration: testcontainers fixture boots stack; healthchecks pass
- E2E: `docker compose up -d && docker compose ps` all healthy within 30s

**HIL script (15 min):** Fresh-clone `qp up`; visit all service ports; `qp down` then `qp up` again; state persists; `qp doctor` output reviewed.

**DoD:** Fresh laptop → functioning skeleton in <5 min.

### M2 — Validation math (target: 3 workdays)

**Deliverable:** Port PBO, DSR, CPCV, walk-forward harness from MVP-A archive to `packages/sdk/quantplatform/validation/`. Pure functions, fully unit-tested.

**Automated tests:**
- Unit: López de Prado reference examples; Bailey 2014 DSR values; CPCV partition counts; property tests for monotonicity, bounds, edge cases
- 100% line coverage on this module

**HIL script (30 min):** Run the test suite; walk through one reference test; read source together; discuss default thresholds for MVP.

**DoD:** Math signed off. User approves "this is what gates promotions."

### M3 — SDK + local runs (target: 4 workdays)

**Deliverable:** SDK module with `Strategy`, `sdk.data.ohlcv`, `sdk.run.start`, content-hashed lineage writes. `qp new strategy hello-world` scaffolds V template. `qp run hello-world` executes on host, logs to MLflow, writes `runs` + `events` + `lineage_reads`. NO gate yet — runs finish without pass/fail decisions.

**Automated tests:**
- Unit: SDK method contracts; lineage record shape; scaffold correctness
- Integration: `qp run` against live stack; MLflow run created; lineage rows written; audit log extended
- E2E: `qp e2e` container build + run passes in <90s

**HIL script (30 min):** Scaffold, run, browse MLflow UI, inspect Postgres lineage, attach debugger, `qp doctor`.

**DoD:** Local run loop complete. Lineage works. Debugger attach confirmed. Container e2e passes.

### M4 — Walk-forward gate + promotion API (target: 3 workdays)

**Deliverable:** Wire walk-forward + PBO/DSR/CPCV into runs. Gate decision emitted as event and tag. `POST /models/<name>/versions/<v>/promote` API endpoint (called by UI in M5; exercised in M4 via `curl` or the Swagger docs). NO CLI verb for promote in MVP. Companion `hello-world-returns` template (expected to fail gate).

**Automated tests:**
- Unit: gate decision logic; promote handler refuses alias flip on fail; `qp check` AST walk catches bypass attempts
- Integration: V passes → promote API succeeds, MLflow alias flips, `ModelPromoted` event emitted; R fails → promote API refuses with 4xx and a blocking-reason message

**HIL script (45 min):** Run V (passes); call promote API via curl, verify MLflow alias flipped. Run R (fails); call promote API via curl, verify refusal with clear reason. Verify audit log has the events hash-chained. **Evaluate failure UX quality**: does the refusal message teach *why* it failed, not just *that*?

**DoD:** V passes the gate and can be promoted via API; R is blocked with a clear, teaching error message. No CLI promotion verb exists.

### M5 — UI happy path (target: 5 workdays)

**Deliverable:** Login, strategies list, runs list, run-detail with walk-forward chart + PBO/DSR/CPCV, Promote button, unified session via `qp up --open-browser`.

**Automated tests:**
- UI (Playwright): login → strategies → run → chart renders → promote succeeds
- Regression: backend tests from M1–M4 still green

**HIL script (30 min):** Browser opens logged-in; navigate to run; review walk-forward chart — *is it readable?*; click Promote; verify MLflow alias flipped; try promoting R (dialog should refuse with the same reason the API returns when called via curl in M4).

**DoD:** Beats 1–5 of journey usable in UI. Walk-forward visualization HIL-approved.

### M6 — Serving + inference + drill-back (target: 4 workdays)

**Deliverable:** Serving role reads MLflow promoted models on `ModelPromoted` events; `POST /serving/<model>/predict`; UI inference form; drill-back screens (inference → model version → training run → dataset versions).

**Automated tests:**
- Integration: promote → serving reloads within 5s; inference latency <200ms cached
- UI: drill-back navigates all hops

**HIL script (45 min):** Run inference; drill all the way back; **evaluate LP-ODD feel** — would Jenny Lin believe an LP could answer ODD questions from these screens?

**DoD:** Journey beats 1–9 end-to-end. Drill-back complete.

### M7 — Accounts service + `qp auth login` (target: 3 workdays)

**Deliverable:** `accounts-api` deployed to ubuntu-server behind Cloudflare Tunnel; GitHub OAuth device flow; `/me`, `/events`; `qp auth login` integration; telemetry client with opt-out.

**Automated tests:**
- Unit: OAuth state machine; token storage; log-redaction
- Integration: device flow end-to-end; telemetry lands in accounts DB; offline-graceful (accounts unreachable → CLI still works, events queue locally up to 100)

**HIL script (30 min):** Login flow; status check; telemetry lands; opt-out respected; simulate accounts outage; inspect `~/.qp/credentials` for leaks.

**DoD:** Auth flows work; telemetry is opt-out-respecting; offline mode functions.

### M8 — Packaging + demo rehearsal (target: 2 workdays)

**Deliverable:** `quantplatform` on PyPI (or TestPyPI); `uv tool install quantplatform` verified; `get.quantplatform.io/install.sh` hosted on ubuntu-server; README quickstart; 5-minute demo video.

**Automated tests:**
- Integration: clean install on matrix (macOS, Linux, Python 3.11/3.12/3.13)
- E2E: cold-install VM test — `curl | sh`, `qp new`, `qp up`, `qp run`, expected output

**HIL script (60 min — the real demo rehearsal):** Clean machine; install; auth login (optional); scaffold; up; run (passes); promote; infer; drill-back; show R (fails); time the whole thing; record video.

**DoD:** Under 10 minutes from `curl | sh` to "model promoted and served inference." Demo video captured. Ready for Jenny Lin.

### 9.1 Milestone aggregate

- Work days: 26 (≈5–6 weeks solo; faster with parallel subagents where safe)
- HIL sessions: 8; ~5 hours of total HIL time
- Go / no-go gates: 8

Calendar slippage between milestones is acceptable. **Skipping or shortening HIL is not.**

## 10. HIL checkpoint template

Each milestone has `docs/milestones/M<n>/hil.md`:

```markdown
# Milestone M<n> — HIL Checkpoint

## Scope of this review
What landed; what deliberately didn't.

## Prerequisites
- Repo at commit <sha>
- All automated tests green (unit / integration / e2e / UI as applicable)
- `qp doctor` clean

## Script
Numbered steps + expected observable outcomes + screenshots / terminal captures.

## Decision points (the HIL judgement calls)
Open questions that automated tests can't answer.

## Sign-off
- [ ] Automated tests green
- [ ] Script ran to completion without surprises
- [ ] Decision points resolved (see notes)
- [ ] User approves proceeding to M<n+1>

## Defects found
- [ ] <classification: MUST-FIX-BEFORE-NEXT / DEFER-TO-V2 / SPEC-UPDATE>

## Spec / plan updates triggered
- [ ] <list>
```

## 11. Feedback capture

When HIL surfaces defects or gaps:
1. Logged as GitHub issues (never just in conversation)
2. Classified: MUST-FIX-BEFORE-NEXT-MILESTONE, DEFER-TO-V2, SPEC-UPDATE
3. Spec updated if a commitment changes
4. Plan updated if a milestone scope shifts
5. Next milestone does not start until all MUST-FIX items close

This is the missing mechanism from MVP-A.

## 12. Success criteria for MVP

The MVP is complete when all of the following are true simultaneously:

- M1–M8 HIL checkpoints all signed off
- `hello-world-vol-har` passes the gate and promotes from a clean install
- `hello-world-returns` is rejected by the gate with a clear error message
- A fresh-laptop demo (install → scaffold → up → run → promote → infer → drill-back) completes in under 10 minutes
- Content-hashed lineage is written on every data read and queryable from both UI and Postgres
- The MLflow alias path is the only promotion mechanism in the code (no `.stage` anywhere)
- The hash-chained audit log passes property tests under simulated concurrency
- Accounts service accepts telemetry events; opt-out is respected; CLI works offline
- Demo video of the happy path is recorded and < 5 minutes long

## 13. Risks and mitigations

| # | Risk | Mitigation |
|---|---|---|
| R1 | Scope creep mid-build (MVP-A failure mode) | HIL gates between milestones; MUST-FIX vs DEFER classification; spec updates require explicit decision, not drift |
| R2 | Pre-push hook too slow → devs disable → drift returns | <90s budget enforced; BuildKit cache + uv cache mount; CI backstop on main |
| R3 | Host-run strategy passes but container-run fails | `qp e2e` in pre-push; M3 HIL explicitly verifies container mode |
| R4 | Bundled demo data produces non-pedagogical outcome (R passes by luck, V fails by data quirk) | Validate in M3–M4 with actual bundled data; regenerate data if needed |
| R5 | Accounts service outage blocks all CLI use | CLI must work offline; telemetry queues locally (cap 100); M7 HIL simulates outage |
| R6 | Walk-forward UI is unreadable → demo fails the "quant would trust this" test | M5 HIL evaluates readability explicitly; redesign before M6 |
| R7 | MLflow `.stage` sneaks into code via copy-paste | `qp check` AST walk in pre-commit; CI grep on main |
| R8 | Strategy code bypasses SDK data access → no lineage | `qp check` AST walk flags `pl.read_*`, `pd.read_*`, `open()`, `requests.get()` |
| R9 | Drift between spec and code during build | Self-review at end of each milestone against spec; diff-log attached to HIL |
| R10 | Subagent work produces divergent conventions | Subagent prompts reference this spec; code-reviewer agent invoked at each milestone merge |

## 14. Out-of-scope futures (captured but not built)

- **Journey B — Platform engineer onboarding** — separate spec; covers repo setup, CI/CD, tenant provisioning, debugging production incidents
- **Journey C — LP / compliance viewer** — separate spec; covers ODD export, audit search, inference drill-down, report generation
- **`qp ai` (Claude Agent SDK)** — `qp ai explain run <id>`, `qp ai suggest-threshold`, `qp ai new-strategy "mean reversion on SPY"`
- **`qp data register`** — BYO-data flow for customer-owned datasets
- **`qp deploy`** — push tenant image to GCP project
- **`qp submit`** — scheduled / background runs via PGMQ
- **`qp watch`** — file-watch hot reload
- **Bi-temporal silver ingestion pipelines**
- **Multi-instrument / cross-sectional example** — e.g., 20 liquid US equities with factor-style signal
- **Homebrew tap** — `freesidenomad/homebrew-tap`
- **Nixtla-based multi-series example** — MLForecast across 50+ instruments
- **Tenant compliance export workflows**
- **Real OIDC federation with Google Workspace / Entra** (currently mock OIDC only in local mode)

## 15. Reference material

- `LESSONS.md` — MVP-A retrospective, informs every reversal in this spec
- `START.md` — this session's kickoff brief; defines the three pillars
- `blueprint/src/01-executive-summary.md` — architectural bets
- `blueprint/src/09-ml-platform.md` — MLflow + walk-forward + pyfunc patterns
- `blueprint/positioning/2026-04-21-positioning.md` — one-sentence pitch, three differentiators
- `blueprint/prd/2026-04-21-quant-platform-v1.md` — product requirements
- `blueprint/sdk/2026-04-21-quant-sdk-design.md` — earlier SDK design; informs but does not constrain
- MVP-A archive at `../deployment/quant-platform-archive-2026-04/` — source for port of PBO/DSR/CPCV math and audit-log pattern
- López de Prado, *Advances in Financial Machine Learning* (Wiley 2018) — PBO, CPCV
- Bailey & López de Prado, "The Probability of Backtest Overfitting," *JCF* 2014 — DSR, PBO

## 16. Non-goals (explicit)

This spec does not:
- Commit to a calendar ship date. It commits to 8 HIL-gated milestones and a workday estimate.
- Lock the SDK surface beyond v0. Breaking changes to the SDK are acceptable up to v1.
- Ship any production-tenant capability. The architecture supports it; MVP does not exercise it.
- Include compliance certifications (SOC 2, ISO 27001). Describes posture; does not audit.
- Replace the blueprint. Refines it for a single journey; blueprint remains the broad reference.

---

**End of spec.**
