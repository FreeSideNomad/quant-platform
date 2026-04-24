# Local Development

## The golden rule

Every production behaviour must be reproducible on a single developer laptop. This is not a target; it is a constraint. Any cloud dependency that cannot be simulated locally is disqualified from the architecture. This constraint is the reason PGMQ replaces Pub/Sub, APScheduler replaces Cloud Scheduler, authlib replaces Identity Platform, and Cloud Workflows is entirely absent from the stack.

The practical test: a new engineer with a reasonably-specced laptop, a fresh checkout of the repository, and no GCP credentials should have a running local instance with seeded data, live authentication, functioning pipelines, and a working model training path in under fifteen minutes. Any PR that breaks this test does not merge.

## The docker-compose stack

![Local development topology](diagrams/rendered/09-local-topology.pdf){width=90%}

Four containers cover the full production dependency set:

1. **`postgres`** — Postgres 16 with AGE, TimescaleDB, PGMQ, and pg_cron extensions pre-loaded. Custom image built from a simple Dockerfile that layers the extensions onto the official Postgres image.
2. **`minio`** — S3-compatible object storage, used as the GCS substitute. The application's storage adapter selects MinIO when the `STORAGE_BACKEND` environment variable is set to `minio`.
3. **`mock-oidc`** — a lightweight OIDC provider simulating the customer's Google Workspace or Entra directory. Either a purpose-built container (the `oidc-provider-mock` image is a common choice) or a tiny FastAPI application maintained in the repository for full control.
4. **`mlflow`** — the MLflow tracking server, backed by the same Postgres instance (distinct schema) and using MinIO for artefact storage.

The application itself runs outside docker-compose during development, under `uvicorn --reload`, so that code changes propagate instantly. For CI and for reproducibility-sensitive integration tests, a fifth `app` service is included in an alternate compose file.

## Emulator conventions

The application code uses environment variables to select between production and local backends. The major Python libraries in the stack all respect well-known emulator conventions:

| Library | Variable | Effect |
| :--- | :--- | :--- |
| `google-cloud-storage` | `STORAGE_EMULATOR_HOST` | Routes all GCS calls to the MinIO endpoint |
| `google-cloud-pubsub` | `PUBSUB_EMULATOR_HOST` | Not used — PGMQ is used instead |
| `mlflow` | `MLFLOW_TRACKING_URI` | Points at the local MLflow container |
| `authlib` (custom) | `OIDC_DISCOVERY_URL` | Points at the mock OIDC provider |

A single `.env` file in the repository root holds development values. Production overrides come from Secret Manager, injected via Cloud Run environment variables. The application code never has conditional logic like `if environment == "local"` — it reads configuration and trusts it.

## The Makefile

All common development operations are Makefile targets, giving engineers a single vocabulary regardless of the underlying tooling:

| Target | Purpose |
| :--- | :--- |
| `make dev` | Bring up the docker-compose stack in the background |
| `make dev-stop` | Stop the docker-compose stack |
| `make migrate` | Apply Alembic migrations against the local Postgres |
| `make seed` | Populate the database with test tenants, users, and sample data |
| `make run` | Start the application under `uvicorn --reload` |
| `make test` | Run the full test suite (unit + integration) against the local stack |
| `make test-unit` | Run only unit tests (no stack required) |
| `make test-e2e` | Run Playwright end-to-end tests against the local stack |
| `make proto` | Regenerate protobuf stubs after schema changes |
| `make openapi` | Regenerate the frontend API client from the OpenAPI spec |
| `make lint` | Run ruff, pyright, and frontend linters |
| `make format` | Auto-format Python and TypeScript |
| `make clean` | Remove build artefacts and stop running services |

New engineers rely on this vocabulary. Senior engineers extend it when new operations become routine. The Makefile is canonical, version-controlled, and tested in CI.

## Seed data

The `make seed` target populates the local database with a reproducible set of tenants, users, models, training runs, and time-series data. Seed data lives in the repository as parquet files and SQL fixtures, not as generated data, so that it is stable across test runs and across developers.

Typical seeds include:

- Two tenants (a healthy one and a degenerate one for edge-case testing)
- A half-dozen users per tenant spanning the role vocabulary
- Three registered models in MLflow with multiple versions each
- Thirty days of synthetic market data in the silver layer
- A handful of failed and successful training runs for status-display exercise
- Inference log entries demonstrating the audit trail

The same seed data is used in integration tests, in Playwright end-to-end tests, and in the demo environment. This reuse ensures that UI layouts, API contracts, and pipeline behaviour are all validated against a consistent fixture set.

## Testing strategy

The test pyramid has three layers:

### Unit tests

Target the domain layer. No I/O, no database, no network. Tests run in tens of milliseconds; the full unit suite runs in under thirty seconds. Coverage goal: every non-trivial business rule has at least one positive and one negative test case.

Frameworks: `pytest`, `hypothesis` for property-based tests where appropriate.

### Integration tests

Target the application's HTTP surface and its persistence behaviour. Use FastAPI's `TestClient` to issue requests against the real application, backed by the docker-compose Postgres, PGMQ, MinIO, and mock OIDC provider. Each test runs in its own database transaction, which is rolled back at the end.

This is the layer that validates that the application actually works end-to-end within a single machine. Every feature has integration tests; every bug fix is accompanied by an integration test that fails before the fix.

### End-to-end tests

Target the user-facing flows through the React UI, driven by Playwright. Run against the same docker-compose stack, with the application running under uvicorn and the frontend running under Vite's dev server. These tests are fewer in number (dozens, not thousands) but exercise real user journeys: login, model submission, training-run monitoring, inference invocation.

Because the entire stack is local, Playwright tests run on every PR in CI without requiring ephemeral cloud environments.

## CI parity

The CI pipeline (GitHub Actions) runs the identical docker-compose stack. Integration tests in CI are not running against a staging environment or ephemeral cloud resources — they are running against the same containers that engineers use locally. This ensures that "works on my machine" and "works in CI" diverge only in obvious, diagnosable ways (resource constraints, GitHub runner flakiness) rather than in subtle behavioural differences.

The CI job that executes `make test` is the single gate on merging to `main`. It runs in approximately five to eight minutes on a standard GitHub-hosted runner.

## Onboarding

The onboarding experience is deliberately polished. A new engineer's first day runs as:

1. Clone the repository.
2. Run `make setup` — uses `uv sync` to install Python dependencies (seconds, not minutes), installs frontend dependencies with `npm ci`, and builds the custom Postgres image.
3. Run `make dev` — brings up the stack.
4. Run `make migrate && make seed && make run` — working application.
5. Open `http://localhost:8000` — log in as a seeded user.

Total elapsed time, assuming dependencies cached: under ten minutes. If any step of this experience takes longer or requires manual intervention, it is treated as a bug and fixed.

This experience is not separate from production readiness — it *is* production readiness. The rigour required to make local development work well is the same rigour that keeps production deployments boring.

## Tooling foundations

The development tooling is chosen for speed and for consistency between local, CI, and container builds:

- **uv** (Astral) manages Python dependencies and virtual environments. `uv.lock` pins exact versions; `uv sync` produces identical environments everywhere. Package resolution and installation are measured in seconds rather than minutes, which materially shifts the feel of the edit-test cycle.
- **ruff** (Astral) handles formatting and linting in a single Rust binary. `make lint` runs in under a second on the full Python codebase. It replaces the conventional stack of black, isort, flake8, pyupgrade, and pydocstyle.
- **pyright** (or Astral's **ty** once generally available) enforces static typing. CI fails on type errors; the local `make lint` target runs the same check.
- The frontend uses **Vite** for the dev server and production build, **eslint** with the flat-config defaults, **prettier** for formatting, and **Vitest** for unit tests.

Every tool listed here is also used in the CI pipeline with the same configuration and the same version pinned in `uv.lock` or `package-lock.json`. "Works on my machine; fails in CI" is eliminated by making the machine and CI use identical toolchains.
