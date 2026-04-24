# System Architecture

## Context

The platform sits between three classes of external system: the customer's enterprise identity provider (Google Workspace or Microsoft Entra), the customer's market and reference data sources (delivered via SFTP, API, or object storage hand-off), and the vendor's operational substrate (GitHub, Google Cloud, and a thin internal control plane used by vendor operations staff).

Users interact with the platform exclusively through a React single-page application served by the application container. All user-facing operations traverse a single REST API; there is no direct customer access to the database, the blob store, or the underlying GCP resources.

![System context](diagrams/rendered/01-system-context.pdf){width=95%}

## Container view

A single customer instance consists of five deployed components:

1. **The application image, deployed as a small set of single-purpose services** — one Docker image stamped from the same codebase, deployed as a set of Cloud Run services that differ only in the `ROLE` environment variable they read at startup: the `api` (REST handlers, React static assets, command dispatch, OIDC callbacks), one service per projector role (`worker-proj-ui`, `worker-proj-graph`, `worker-proj-analytics`), one per pipeline worker role (`worker-pipeline-bronze`, `worker-pipeline-silver`), the `worker-training` job dispatcher, the `worker-inference-batch` processor, and the `scheduler` daemon. Every service runs the same image and shares the same database connection patterns; they differ only in role, autoscaling policy, and IAM bindings. The `api` service runs with a minimum of one always-warm instance; worker services autoscale on queue depth (see Application Architecture chapter for the full role table). The full role table and rationale are in the Application chapter.

2. **Postgres (Cloud SQL by default; AlloyDB where required)** — the operational data store, event log, queue, graph, and time-series backend. Configured with the AGE, TimescaleDB, PGMQ, and pg_cron extensions. Cloud SQL is the default; AlloyDB is required only if AGE or PGMQ are not available on Cloud SQL's supported extension list in the deployment region. The Infrastructure and Application chapters reference this rule rather than restating it.

3. **Object storage (GCS)** — raw ingested files (bronze layer), model artefacts, training datasets, and inference batch outputs. Accessed via a storage abstraction that binds to MinIO in local development.

4. **MLflow tracking server** — model experiment tracking, run metadata, and model registry. Backed by the same Postgres instance (separate schema) and uses GCS as the artefact store. Deployed as a separate Cloud Run service to isolate its upgrade cadence from the main application.

5. **Static frontend** — the React SPA, served either from the application container (simpler, adequate for moderate traffic) or from a CDN-fronted GCS bucket (lower latency, preferred for production). Both paths are supported by the same build artefact.

![Container diagram](diagrams/rendered/02-container-diagram.pdf){width=95%}

## Components within the application

The application container is logically partitioned into modules that share a single Python process and a single database connection pool but maintain clear boundaries at the code level.

- **API surface** — REST handlers for user-facing commands and queries, plus internal webhook endpoints that receive PGMQ push deliveries and OIDC callbacks.
- **Domain** — pure Python business logic: aggregates, commands, events, invariants. No I/O; no framework dependencies.
- **Projections** — handlers that consume events from PGMQ queues and update read models in Postgres tables, AGE graphs, and TimescaleDB hypertables.
- **Pipelines** — ingestion and transformation functions organised in medallion layers, invoked by the scheduler or by event triggers.
- **Training** — model training orchestration that coordinates data extraction, training job dispatch, artefact persistence, and model registration.
- **Serving** — model inference endpoints that load versioned models from the MLflow registry and expose them through the REST API.
- **Infrastructure adapters** — database sessions, PGMQ client, blob store client, MLflow client, identity provider client. All pluggable by environment.

## Technology stack summary

Technology choices reflect current best-in-class options across the Python and data-engineering ecosystem as of 2026. Where a newer option has meaningfully displaced an older default (uv replacing pip/poetry, Polars replacing pandas, Nixtla replacing ad-hoc time-series code), the newer option is preferred.

### Application runtime

| Concern | Component | Rationale |
| :--- | :--- | :--- |
| Web framework | **FastAPI** | Async-native, Pydantic-v2 integrated, first-class OpenAPI; widely adopted across the Python ecosystem. Ecosystem dominance over Litestar discussed below in "Why these choices over common alternatives" |
| ASGI server | **uvicorn** (with `--workers` in production) | Reference ASGI server; Granian is a contender but uvicorn remains the default |
| Validation | **Pydantic v2** | Rust-backed validators, schema generation, FastAPI integration |
| Data-frame validation | **Pandera v3** | Schema-first DataFrame validation; first-class Polars support |
| Data frames | **Polars** | Rust-backed, lazy evaluation; on the bulk transformation workloads typical of this platform (silver/gold group-bys and joins on multi-million-row frames), order-of-magnitude faster than pandas with materially better memory characteristics (per the Polars project's published benchmarks at pola.rs/benchmarks). Pandas retained at integration points with libraries that require it |
| In-memory analytics | **DuckDB** (optional) | Columnar analytics engine; Arrow-native interop with Polars. Used where complex analytical queries against in-memory datasets outperform round-trips to Postgres |
| HTTP client | **httpx** | Async-native, drop-in replacement for requests |
| Task scheduling | **APScheduler** | In-process cron; durable via Postgres job store. Triggers Dagster materialization runs on schedule and handles the cron cases that do not warrant an asset |
| Pipeline orchestration | **Dagster** | Software-defined-asset model, lineage, asset checks, and a visual DAG UI. Run storage reuses the existing Postgres instance; deployed as a docker-compose service locally and a Cloud Run service in production. The UI is proxied read-only via the BFF under `/dagster/*` |

### Data platform

| Concern | Component | Rationale |
| :--- | :--- | :--- |
| Database | **Postgres 16** | Foundation for all operational data; extensions cover specialised needs |
| Graph | **Apache AGE** extension | Cypher inside Postgres; no separate graph database |
| Time series | **TimescaleDB** extension | Hypertables, compression, continuous aggregates inside Postgres |
| Message queue | **PGMQ** extension | Transactional with state changes; no separate broker |
| DB scheduler | **pg_cron** extension | In-database cron for maintenance and materialised-view refresh |
| DB driver | **asyncpg** (direct) + **SQLAlchemy 2.x async** (ORM) | Raw async for hot paths, ORM for CRUD and migrations |
| Migrations | **Alembic** | Standard; supports async SQLAlchemy |
| Blob storage | **GCS** (prod), **MinIO** (local) | S3-compatible; abstracted by application adapter |
| Object client | **google-cloud-storage** (respects `STORAGE_EMULATOR_HOST`) | Single client for both environments |

### ML platform

| Concern | Component | Rationale |
| :--- | :--- | :--- |
| Experiment tracking & registry | **MLflow 2.x** | Open-source, Postgres-backed, full local stack |
| Model packaging | **MLflow `pyfunc`** | Captures serialisation + inference wrapper in one artefact |
| Classical ML | **scikit-learn**, **XGBoost**, **LightGBM**, **CatBoost** | Best-in-class for tabular quantitative workloads |
| Time-series forecasting | **Nixtla suite** (StatsForecast, MLForecast, NeuralForecast, HierarchicalForecast), **Darts** | Leading Python ecosystem for classical, ML, and deep time-series; hierarchical reconciliation first-class |
| Foundation models for TS | **TimeGPT** (optional) | Pre-trained time-series foundation model; useful for cold-start scenarios |
| Deep learning | **PyTorch 2.x** (default) or **JAX** (research-led teams) | PyTorch for production; JAX where the customer's research team is already there |
| Backtesting | **vectorbt** / **vectorbtpro**, **QSTrader**, **LEAN** | Current leading vectorised and event-driven frameworks; choice driven by strategy shape |
| Quant numerics | **NumPy**, **SciPy**, **QuantLib** (where derivatives pricing applies) | Standard foundation |
| Hyperparameter search | **Optuna** | Async-friendly, MLflow-integrated, current default |

### Frontend

| Concern | Component | Rationale |
| :--- | :--- | :--- |
| Framework | **React 19** | Industry standard; server components optional for SSR variants |
| Build tool | **Vite** | Dominant dev-server and build pipeline |
| Router | **TanStack Router** | Type-safe, preferred default for new React projects in 2026 |
| Data fetching | **TanStack Query** | Cache, mutations, background refetch; current default for server state |
| UI primitives | **shadcn/ui** (Radix + Tailwind v4) | Copy-paste components; direct ownership of UI code |
| Forms | **react-hook-form** + **zod** | Typed, performant forms with schema validation |
| API client | Generated from OpenAPI via **openapi-typescript** | Zero drift between server and client contracts |

### Identity and security

| Concern | Component | Rationale |
| :--- | :--- | :--- |
| OIDC | **authlib** | Mature, standards-compliant, framework-agnostic |
| JWT | **PyJWT** | For session JWT minting and verification |
| Secret store (prod) | **Secret Manager** | Per-tenant IAM-scoped |
| Secret store (local) | `.env` via **python-dotenv** | Single line of environment-aware config |

### Infrastructure and delivery

| Concern | Component | Rationale |
| :--- | :--- | :--- |
| Application runtime | **Cloud Run** | Stateless container, min-instance support, revision-based rollout |
| Job runtime | **Cloud Run Jobs** (CPU), **Vertex AI Custom Training** (GPU) | Single dispatch interface |
| Image registry | **Artifact Registry** | IAM-integrated, vulnerability scanning |
| Infrastructure as code | **Terraform** | Per-tenant modules; state in GCS |
| CI/CD | **GitHub Actions** + **Workload Identity Federation** | No long-lived keys |
| Container base | **Chainguard Python** or **Distroless** | Minimal attack surface, continuously patched upstream |

### Tooling

| Concern | Component | Rationale |
| :--- | :--- | :--- |
| Package manager | **uv** (Astral) | Order-of-magnitude faster than pip/poetry on cold and warm installs (per Astral's published uv benchmarks); lockfiles, workspaces, Python version pinning; the current default for new Python projects in 2026 |
| Linter/formatter | **ruff** (Astral) | Replaces flake8, black, isort, pyupgrade, etc. in one Rust binary |
| Type checker | **pyright** (or Astral's **ty** once GA) | Strict typing enforced in CI |
| Testing | **pytest**, **pytest-asyncio**, **hypothesis** | Unit + property-based |
| Integration testing | **testcontainers-python**, FastAPI **TestClient** | Real services in docker, real HTTP against the app |
| E2E testing | **Playwright** | Real browser, headless in CI |
| Observability | **OpenTelemetry** (Python SDK + Collector sidecar) -> **Cloud Logging** / **Cloud Monitoring** / **Cloud Trace** | Open standard, GCP-native sinks |

### Why these choices over common alternatives

- **Polars over pandas**: for the workloads typical of this platform — bulk silver/gold transformations, group-bys, joins on multi-million-row frames — Polars is materially faster than pandas and has substantially better memory characteristics. Its lazy API produces query plans that optimise across operations. Pandas remains acceptable at integration points with libraries that require it.
- **uv over pip/poetry/rye**: uv is orders of magnitude faster, handles Python version management, and has stable lockfile semantics. Container builds see minutes shaved off. Astral's continued stewardship and rapid release cadence secure its trajectory.
- **Nixtla suite over hand-rolled time-series pipelines**: the Nixtla libraries cover the full lifecycle (statistical, ML, neural, hierarchical) with a consistent API, are benchmarked against academic baselines, and are production-grade. Reinventing any part of this stack is no longer justified.
- **PGMQ over Redis/Kafka/Pub-Sub**: shares the transactional boundary with the state changes it announces; removes an entire class of dual-write inconsistency.
- **TanStack Query + Router over Redux / React Router**: TanStack's API is the preferred default for data-fetching and client routing in 2026 and is substantially smaller to learn and maintain.
- **FastAPI over Litestar**: Litestar's raw throughput is higher, but the ecosystem, documentation, and hiring pool for FastAPI are decisively larger, and the throughput gap is irrelevant at realistic request rates for this market.
- **Dagster over Airflow / Prefect, alongside APScheduler and PGMQ**: the three concerns coexist rather than compete. PGMQ carries the CQRS command-and-event flow because it shares the transactional boundary with state changes (no dual-write problem). APScheduler handles in-process cron, including the cron triggers that hand work off to Dagster. Dagster owns the data-and-ML asset graph: bronze, silver, and gold layers as software-defined assets, training runs and model versions as dynamic per-strategy assets, asset checks as first-class data-quality enforcement. Dagster's asset model is the visual lineage view an LP allocator wants to see during operational due diligence; that alone earned it a place in v1. Airflow's task-graph model is task-centric rather than asset-centric and a poorer fit for medallion data; Prefect is a credible alternative, but Dagster's asset checks and lineage UI are decisive for this market.

## Data flow at a glance

A user action in the React UI issues a REST call to the API. The API validates the JWT session token, resolves the tenant context, and dispatches a command to the domain layer. The command handler performs its validation, writes events to the event store, enqueues projection messages to PGMQ queues, and updates aggregate state — all within a single Postgres transaction.

Projection workers — running as separate Cloud Run services, one per projector role, each stamped from the same image with a distinct `ROLE` env var — consume their respective queues, transform events into read-model updates, and commit those updates to their target tables, graphs, or hypertables. Each worker implements internal concurrency via asyncio tasks, but does not co-reside with the API process. Subsequent user queries read from these projections.

In parallel, ingestion pipelines fetch data from external sources, land it in bronze (GCS), transform and validate it into silver (Postgres), and aggregate it into gold (Postgres). Training pipelines extract data from gold, run model training jobs (on Cloud Run Jobs or Vertex AI for GPU workloads), and register the resulting artefacts in MLflow. Serving endpoints load registered models and expose inference through the API.

Every step emits structured events. Every event is idempotent, versioned, and reversible by replay.
