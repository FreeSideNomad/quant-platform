# Application Architecture

## Single image, multiple roles

The application is built, shipped, and operated as a single Docker image. That image, when instantiated, picks a **role** from an environment variable at startup and behaves accordingly. Roles supported in a typical deployment:

| Role | Responsibility | Deployed as |
| :--- | :--- | :--- |
| `api` | HTTP request/response, command dispatch, query serving, OIDC callbacks | Cloud Run service, autoscaled by HTTP request rate |
| `worker-proj-ui` | Projects events into the UI read-model tables | Worker service, autoscaled by `proj_ui` queue depth |
| `worker-proj-graph` | Projects events into the AGE graph | Worker service, autoscaled by `proj_graph` queue depth |
| `worker-proj-analytics` | Projects events into TimescaleDB aggregate tables | Worker service, autoscaled by `proj_analytics` queue depth |
| `worker-pipeline-bronze` | Handles bronze-arrival events, triggers silver transforms | Worker service, autoscaled by `ingest_bronze` queue depth |
| `worker-pipeline-silver` | Silver-to-gold transformation | Worker service, autoscaled by `ingest_silver` queue depth |
| `worker-training` | Training job dispatch and status polling | Worker service, autoscaled by `training` queue depth |
| `worker-inference-batch` | Batch inference job processor | Worker service, autoscaled by `inference_batch` queue depth |
| `scheduler` | APScheduler daemon emitting periodic messages | Single-instance service, min=1 max=1 |

Every role is the same image. The same test suite. The same build. The same deployment pipeline. The difference is the `ROLE` environment variable.

The application's `main` module reads the role on startup, sets up the appropriate components (FastAPI ASGI app for `api`; asyncio worker loops for `worker-*` roles; APScheduler for `scheduler`), and begins its loop. Because the image is identical, a developer can run any role locally with a simple environment variable change and can be confident that what runs locally matches what runs in production.

## Rationale

The two alternatives commonly proposed for this problem space are explicitly rejected.

**Scattered serverless** — one Cloud Function or Cloud Run service per task, each with its own repository, its own CI/CD pipeline, its own dependency list. Fragments the codebase, makes local development heavy, multiplies operational surface, and typically introduces duplicate implementations of cross-cutting concerns (logging, auth, database access). The worst version of this pattern is a team maintaining forty cloud functions across five repositories, none of which are individually testable end to end.

**Single-process kitchen sink** — one `uvicorn` process hosting the API plus every worker as an asyncio task. Simpler to set up; fatal in production. Workers cannot scale independently of the API; backpressure on one worker starves the rest; queue-depth autoscaling has no lever to pull because the worker capacity is pinned to whatever the API container can support. Adequate for a prototype, inadequate for a production platform.

The single-image-multi-role pattern is the middle path that mature distributed systems converge on. It preserves the codebase simplicity of a monolith (one test suite, one build, one deployment) while providing the runtime independence of microservices (one scaling policy per workload, one failure domain per role, one observability scope per concern).

## Role selection and startup

The application's entry point is `python -m app.main`. The `main` module:

1. Reads the `ROLE` environment variable (default: `api`).
2. Loads configuration (database connection, Secret Manager bindings, MLflow URL) — common to all roles.
3. Performs health-check bootstrap (connects to Postgres, verifies extensions, confirms MinIO/GCS access) — common to all roles.
4. Branches on role:
   - `api` -> starts `uvicorn` hosting the FastAPI app
   - `worker-*` -> starts the specified worker loop as an asyncio task, plus a minimal HTTP health-check endpoint for Cloud Run or GKE probes
   - `scheduler` -> starts APScheduler with the job registry plus a health-check endpoint

Each branch shares the application-level observability setup: structured logging with a `role` label, OpenTelemetry tracing, Cloud Monitoring metrics export. A log line from any role is instantly identifiable by the `role` field.

## Command-Query Responsibility Segregation

The write and read paths are separated. Commands are handled by the `api` role in the main request-response path; read models are maintained by the `worker-proj-*` roles consuming events from PGMQ queues.

### Command path

A user action flows as:

1. The REST handler (running in the `api` role) receives the request, validates the input via Pydantic schemas, and constructs a command object.
2. A command dispatcher loads the relevant aggregate from the event store (by replaying events or by loading a snapshot).
3. The aggregate applies domain invariants and produces a sequence of events.
4. Within a single Postgres transaction:
   - The events are appended to the `events` table.
   - The aggregate's state snapshot is updated.
   - Messages are enqueued to each PGMQ queue that serves a read model dependent on these events.
5. The transaction commits atomically, or the entire operation fails.

The transactional outbox pattern is trivialised because PGMQ lives in the same database as the event store. There is no separate broker to synchronise with, no outbox relay process, no dual-write problem.

![CQRS command and projection flow](diagrams/rendered/04-cqrs-flow.pdf){width=95%}

### Projection path

Each read model is served by a dedicated worker role (`worker-proj-ui`, `worker-proj-graph`, `worker-proj-analytics`). That worker runs an asyncio loop that polls its PGMQ queue with a visibility timeout, processes messages in parallel up to a configured concurrency, updates its target read model, and acknowledges.

Projector workers are horizontally scaled. Multiple replicas of `worker-proj-graph` can consume the same queue concurrently; PGMQ's visibility timeout prevents double-processing. When the `proj_graph` queue depth grows, the autoscaler adds replicas; when it drains, replicas scale down.

Projectors are idempotent. Each maintains a `processed_events` table keyed by `(projector_name, event_id)` with a uniqueness constraint. Reprocessing is safe; rebuilding a projection from scratch is truncating its state tables and resetting its watermark.

## Worker anatomy

Every worker role follows the same structure:

- **Startup** — load configuration, connect to Postgres, register the worker's queue name(s) with the PGMQ client.
- **Main loop** — `pgmq.read(queue, vt=N, qty=K)` to pull a batch; process the batch with bounded concurrency using `asyncio.gather` plus a semaphore; on success, `pgmq.delete(queue, msg_id)`; on failure, let the visibility timeout expire and the message will be redelivered.
- **Retry and DLQ** — after the configured retry count, the message is archived to a dead-letter table with the failure reason.
- **Graceful shutdown** — on SIGTERM, stop pulling new messages, finish in-flight processing, then exit. Cloud Run and GKE both respect the termination grace period.
- **Health checks** — a minimal HTTP endpoint (usually port 8080) returns 200 when the worker is healthy, 503 when unable to reach Postgres or stuck. Cloud Run and GKE use this for liveness and readiness probes.

The base Worker class implements all of this. Specific worker roles subclass it and provide only a `handle(message)` coroutine; the registry file maps role names to handlers.

## REST API structure

The API surface is organised into routers by concern:

| Router | Path prefix | Purpose |
| :--- | :--- | :--- |
| Authentication | `/auth` | OIDC login, callback, token refresh, logout |
| Commands | `/commands` | State-mutating actions |
| Queries | `/queries` | Read access to projections |
| Training | `/training` | Model training submission and status |
| Serving | `/serving` | Model inference endpoints |
| Admin | `/admin` | User management, role assignment, tenant configuration |
| Internal | `/internal` | Health checks, worker status, PGMQ dead-letter inspection |

Every route carries an OpenAPI specification generated by FastAPI. The React client is generated from the OpenAPI spec using `openapi-typescript`, keeping the client-server contract in lockstep.

## Domain model

The domain layer contains no framework or infrastructure dependencies. Aggregates are Python classes with pure methods. Events and commands are Pydantic models. Domain tests exercise business rules with plain function calls — no database, no HTTP, no workers.

Typical aggregates:

- **Model** — a trained quantitative model with a version history, lifecycle state (draft, validated, promoted, retired), and owning team.
- **Dataset** — a versioned snapshot of input data, with lineage to bronze sources.
- **TrainingRun** — a single execution of a training pipeline with inputs, outputs, metrics, and reproducibility metadata.
- **Scenario** — a what-if analysis request carrying a model version, input dataset, and result set.
- **RiskLimit** — a threshold (VaR, position, drawdown) that scenarios and live inference checks are validated against.

Aggregates emit events that are versioned, immutable, and replayable.

## React frontend

The frontend is a single-page application built with Vite, consuming the REST API exclusively. It is deployed as static assets — HTML, JavaScript, CSS — produced by the frontend build.

Two hosting options are supported by the same build artefact:

1. **Served by the `api` role** — static files bundled into the container, served by a FastAPI static-files middleware at the root path. Simpler operations, a single deployable, adequate for customer-scale traffic.
2. **Served by Cloud CDN** — static files uploaded to a GCS bucket, fronted by Cloud Load Balancing with Cloud CDN. Lower first-byte latency, cacheable edge delivery. Preferred for larger customer bases.

Either way, authentication cookies are scoped to the application's domain, and API calls are same-origin. There is no separate frontend domain, no CORS configuration, and no cross-site cookie handling.

## Testability

Every layer has a clear test seam:

- **Unit tests** exercise the domain layer with no I/O. Hundreds of tests running in seconds.
- **Integration tests** exercise the API, persistence, and projection layers against the docker-compose stack — real Postgres, real PGMQ, real MinIO. Every production code path is tested here.
- **Contract tests** validate that old events still deserialise after schema migrations and that the OpenAPI specification matches the generated frontend client.
- **End-to-end tests** drive the React UI against a spun-up local stack using Playwright.

No test relies on cloud access. No test uses mocks where a real component is available locally.

## Local development and role execution

Locally, each role can be run in its own container (true production parity) or, for convenience during the fastest inner development loop, multiple roles can run in one process with asyncio tasks. Both modes are supported by the same image. The `make dev` target brings up the docker-compose stack and starts the `api` role plus one replica of each worker role; the `make dev-fast` target runs all roles in a single process for engineers who want faster restart cycles at the cost of production parity. The local development chapter describes this in detail.
