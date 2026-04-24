# Build Sequence

## Principle: sequence, not schedule

The usual reflex in a blueprint is to propose a calendar — weeks per phase, milestones at months, a Gantt chart. That reflex assumes human implementation speed, and it does not survive contact with an agentic development environment in which Claude Code is the primary implementor. The constraint is no longer engineer-hours. The constraints are prerequisite order (what must exist before what), architectural integrity (decisions made in one phase that must not be unmade in a later phase), and feedback loops (what must be testable before the next phase can be planned with confidence).

This chapter describes the build sequence as a directed graph of work, with each phase defined by its prerequisites and its acceptance condition rather than by elapsed time.

## Phase 0 — foundations

**Acceptance condition:** a fresh repository checkout runs end to end locally via a single Makefile target, with authentication, a representative command path, a representative query path, and a smoke training run all exercising real code against local containers. CI executes the same flow against the same container definitions and returns a green status.

**Scope:**

- Repository structure: Python package layout, React frontend scaffold, Makefile target vocabulary, Dockerfile, docker-compose stack with Postgres (all extensions), MinIO, MLflow, Dagster (run storage in the same Postgres), mock OIDC
- Alembic migration scaffold with an initial schema covering events, aggregates, PGMQ queues, user and role tables, audit log
- Seed data fixtures (parquet files and SQL inserts) representing a working tenant
- FastAPI application skeleton: auth router, one placeholder command endpoint, one placeholder query endpoint, health check, OpenAPI generation
- React SPA skeleton: login flow, authenticated shell, route structure matching the API
- Structured logging, OpenTelemetry metrics and tracing instrumentation
- CI/CD pipeline: PR checks, main workflow, container build and publish to Artifact Registry, Workload Identity Federation
- Terraform module for a tenant project (provisioning of Cloud Run, Cloud SQL, GCS, Secret Manager, IAM)

**Prerequisites:** none. This phase is entered from a blank slate.

**Why first:** the foundations establish the test harness against which every subsequent phase will be validated. Phase 0 is not customer-visible; it is the scaffolding that makes every later phase fast and safe. Shortening this phase is a false economy.

## Phase 1 — minimum viable platform

**Acceptance condition:** one real customer performs one real workflow end to end — authenticate, ingest a data file, train a model, promote it, invoke inference, inspect the audit trail — against a production deployment.

**Scope:**

- OIDC federation with the first customer's identity provider (Google Workspace or Entra)
- Role-based authorisation with an initial role vocabulary (quant, risk, admin, viewer)
- File-based ingestion for one source (SFTP pull or GCS drop), bronze landing, silver transformation, gold aggregation
- Model training orchestration with a single compute target (Cloud Run Job) and MLflow integration
- Synchronous model serving for one registered model through the REST API
- Point-in-time correctness enforced in the training data extraction path
- React UI screens covering the golden-path journey
- Playwright end-to-end coverage of the golden-path journey
- First production tenant provisioned by an engineer running `terraform apply` directly against the per-tenant module and live (the control plane that automates this provisioning flow is introduced in Phase 5)

**Prerequisites:** Phase 0 complete.

**Why this scope:** the goal is to exercise every architectural layer in production — authentication, data platform, model training, model serving, audit — rather than to ship a feature-rich product. Every subsequent phase adds depth to layers already proven. A feature missed in Phase 1 is cheap to add later; an architectural gap discovered in Phase 5 is expensive.

## Phase 2 — training depth

**Acceptance condition:** the platform supports the realistic compute profiles of the target customer segment, including GPU training and walk-forward validation that gates model promotion.

**Scope:**

- GPU training dispatch through Vertex AI Custom Training, using the same training orchestration surface
- Walk-forward validation harness that replays historical dates with strict point-in-time data and produces out-of-sample performance metrics
- Model validation gates that block promotion on failed statistical tests, backtest underperformance, or compliance rule violations
- Hyperparameter search coordination with MLflow comparison views
- Model lineage: every trained model is linked to its training dataset snapshot, its code commit, its validation report

**Prerequisites:** Phase 1 complete; a customer with a training workload exceeding Cloud Run Job limits.

## Phase 3 — data pipeline breadth

**Acceptance condition:** the platform ingests data from the full set of source types common to the target customer segment and exports results in the formats those customers demand.

**Scope:**

- File-based ingestion for the full source matrix: SFTP pull, GCS push drop, HTTPS API pull, scheduled vendor API calls
- File-based export: scheduled output files to customer-accessible GCS buckets, SFTP push to customer endpoints, on-demand signed URL downloads
- Per-source data quality validation with quarantine routing and configurable thresholds
- Bi-temporal data pattern applied across silver and gold tables
- Reconciliation jobs producing automated daily comparisons between bronze, silver, and gold layer row counts and key aggregates
- Backfill tooling — a CLI and a minimal UI — for re-running pipeline ranges after source corrections

**Prerequisites:** Phase 1 complete; identification of at least three distinct source types across existing customers.

## Phase 4 — serving breadth

**Acceptance condition:** the platform supports the three inference modes (synchronous, batch, scheduled) with appropriate quality-of-service for each, and supports model version promotion without customer-perceptible disruption.

**Scope:**

- Batch inference endpoints consuming files or dataset references and producing GCS outputs
- Scheduled inference pipelines (e.g. end-of-day scoring, overnight risk calculation) integrated with APScheduler
- Dedicated Cloud Run services for high-QPS or GPU-bound inference, auto-routed from the main application
- A/B traffic splitting between model versions for champion-challenger testing
- Canary inference — new model versions serving a small traffic fraction with statistical comparison before full promotion
- Inference audit trail queryable from the UI and exportable on demand

**Prerequisites:** Phase 1 complete; a customer with serving requirements beyond low-QPS synchronous inference.

## Phase 5 — fleet operations

**Acceptance condition:** adding a new tenant is an operator action rather than an engineering project, and upgrading the fleet to a new release is an orchestrated process that runs unattended within defined safety bounds.

**Scope:**

- Control plane application with tenant registry, provisioning dashboard, and per-tenant telemetry
- Automated tenant provisioning — operator fills a form, control plane drives Terraform, tenant is live within its SLA
- Automated upgrade orchestration with wave-based rollouts (canary, early-adopter, general, conservative) and per-tenant maintenance windows
- Per-tenant customer-accessible dashboards (Cloud Monitoring IAM grants plus optional embedded views in the UI)
- Per-tenant cost attribution pulling from BigQuery billing export
- BYOC support: Terraform module executed under customer-granted service accounts, customer-owned state buckets, documented IAM grant template

**Prerequisites:** Phases 1, 3, and 4 complete; at least three tenants in production to expose fleet-management friction that is invisible with one tenant.

## Phase 6 — compliance surface

**Acceptance condition:** the platform carries the certifications and demonstrable controls required by the contractually-demanding segment of the target market.

**Scope:**

- SOC 2 Type II readiness: control definitions, evidence collection automation, external audit preparation
- Cryptographic chaining of the audit trail and tamper detection job
- WORM retention configuration for audit and inference logs with Object Lifecycle Lock
- Self-service export endpoint producing signed, timestamped archives for regulator requests
- CMEK (Customer-Managed Encryption Keys) support for tenants demanding it
- Additional regional deployments (UK, EU, APAC) as driven by customer demand
- Formal penetration testing cadence and remediation workflow

**Prerequisites:** Phase 5 complete; a customer whose contract terms require any of the above.

## Dependency graph

The phases are not strictly linear. Phase 2 (training depth) and Phase 3 (pipeline breadth) are independent — either may be entered immediately after Phase 1, driven by whichever real customer need surfaces first. Phase 4 (serving breadth) depends on Phase 1 but not on Phase 2 or Phase 3. Phase 5 depends on operational evidence that can only be obtained after at least Phases 1, 3, and 4 are exercised against multiple customers. Phase 6 is gated by customer demand and by the cumulative maturity of Phases 1 through 5.

A project that optimises purely for demonstrable progress rather than architectural integrity is tempted to skip Phase 0 and parallelise Phases 2 through 4. This is the wrong trade. Phase 0 is the test harness; Phases 2 through 4 are features that share the test harness; Phase 5 is the graduation from "product that works" to "service that scales." Respecting the dependency graph produces a system that stays coherent at Phase 6; ignoring it produces a system that requires a rewrite between Phase 4 and Phase 5.

## What gets deferred, and when to revisit

Earlier drafts of this blueprint deferred a dedicated orchestration framework (Dagster, Prefect, or Airflow) on the grounds that APScheduler plus PGMQ covered the pipeline graph for realistic customer scale. That deferral has been reversed: Dagster is in v1, used as the data-and-ML asset orchestrator. The decisive factor was the asset-graph lineage UI, which is the visual artefact LP allocators want to see during operational due diligence and which APScheduler plus PGMQ alone cannot produce. Prefect and Airflow remain not pursued; the asset model in Dagster is a better fit for the medallion data shape than Airflow's task graph, and the asset-check surface is the canonical place to encode data-quality rules. The Data Platform chapter documents the integration in full.

The remaining deferrals continue to sit outside the phase plan until specific conditions make them earn their place:

| Component | Deferred because | Revisit when |
| :--- | :--- | :--- |
| Feature store (Feast) | Quant customers typically embed feature extraction in model code | Train-serve skew becomes a recurring incident source, or cross-model feature reuse is explicitly requested |
| Kubernetes (GKE) | Cloud Run + Vertex AI covers every computed profile | Customer demands stateful workloads, custom sidecars, or a topology Cloud Run cannot express |
| Dedicated broker (Kafka / Confluent) | PGMQ handles realistic message rates | Sustained throughput approaches PGMQ's ceiling, or multi-subscriber replay semantics become essential |
| BigQuery | Postgres + TimescaleDB covers operational analytics | Tick-level data or multi-year backtests require query performance Postgres cannot deliver |
| Dedicated serving platform (Triton / BentoML / Seldon) | In-process serving covers target latency and throughput | Specific customers require GPU inference at QPS the main application cannot handle |

Each deferral is recorded in the repository's `DECISIONS.md` alongside the revisit trigger. When the trigger fires, the component is reconsidered, not automatically added.

## Acceptance discipline

Each phase ends when its acceptance condition is satisfied. The acceptance condition is binary: it is true or it is false. Partial completion is carried forward into the next phase only when the unmet portion does not block the acceptance condition of any subsequent phase. A phase that declares itself complete with unmet acceptance conditions imports debt into the foundation on which every later phase depends; the discipline is to hold the line.

This discipline is especially important in an agentic implementation context, because the temptation to declare completion based on "most of the scope delivered" is amplified by the speed of iteration. The acceptance condition is the ground truth; the scope is the means to the condition, not a substitute for it.
