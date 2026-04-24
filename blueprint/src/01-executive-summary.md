# Executive Summary

## What this document describes

A reference architecture for a Software-as-a-Service platform that allows hedge funds to productionalise their own quantitative models — ingesting data, training models, serving inferences, producing audit trails, and delivering outputs back to customer systems — without each customer having to build the surrounding engineering stack.

## Who the target customer is

Systematic and multi-strategy hedge funds, and the quantitative arms of larger asset managers. These organisations employ quant researchers who build models in notebooks and colleagues who struggle to promote those models to production reliably. They are prepared to pay enterprise prices for a platform that closes that gap, and they demand strong data isolation, compliance posture, and integration with their existing identity and data infrastructure.

Public industry research frames the opportunity concretely: industry capital-introduction surveys consistently report that quantitative strategies are among the most-favoured hedge-fund allocations heading into 2026, and that separately managed accounts — structures which require deploying dedicated instances per mandate — are an increasingly common allocation vehicle for institutional investors. Leading quant managers publicly describe their engineering edge in terms of strict research-to-production environments, model governance, and automated golden paths from research to production.

## The architectural bets

1. **Silo tenancy.** Each customer receives a dedicated instance in their own GCP project, or in a customer-owned GCP project under the Bring-Your-Own-Cloud model. Tenant isolation is infrastructure isolation, not a runtime filter. Application code has no notion of tenants.

2. **Local-first development.** Every production behaviour is reproducible on a developer laptop via docker-compose. Services that cannot be simulated locally are disqualified from the architecture. This constraint shapes every other choice.

3. **Single image, multiple roles.** One Docker image built from one codebase is deployed as many services — the API, each projector worker, each pipeline worker, the training orchestrator, the batch inference worker, the scheduler. Role is selected at startup. Workers autoscale on queue depth independently of the API. Scattered serverless (one function per task) and single-process kitchen-sink (one process with everything as asyncio tasks) are both rejected.

4. **Postgres as the operational substrate.** Event store, work queue, graph store, and time-series store are all Postgres extensions (PGMQ, Apache AGE, TimescaleDB, pg_cron). Blob storage in GCS is the only state outside Postgres. Transactional outbox becomes trivial because the queue shares the database.

5. **Command-Query Responsibility Segregation.** Commands emit versioned events in a single transaction that also writes to state and to queues. Projectors rebuild read models from the event log. The event log is the system of record.

6. **Medallion data platform, file-first.** Bronze (raw files in GCS, content-hashed), silver (validated typed tables in Postgres with bi-temporal lineage), gold (domain aggregates). Inputs and outputs are files by default, matching the reality of hedge-fund integrations.

7. **Research-to-production code parity.** The Python callable used at training time is the same callable used at serving time, packaged into the model artefact. Look-ahead bias and train-serve skew are closed at the pipeline level, not left to researcher discipline.

8. **Customer identity federation.** Customers authenticate through their own Google Workspace or Microsoft Entra directories. The platform issues short-lived session JWTs with application-specific roles, mapped from external claims at login time. No user passwords are stored.

9. **Blue/green deployment via Cloud Run revisions.** Each release is a new revision; traffic shifts in stages; rollback is a traffic-configuration change. Forward-compatible schema migrations make this safe.

10. **Control plane as an internal product.** A separate application operated by the vendor's operations team provisions tenants, orchestrates upgrade waves, and aggregates fleet telemetry. Silo tenancy is operationally viable only because the control plane treats tenant lifecycle as automation rather than manual toil.

## Technology choices, briefly

The Python runtime stack uses the current best-in-class tooling as of 2026: `uv` for packaging, `ruff` for lint and format, `pyright` for types, FastAPI for the web framework, Pydantic v2 for validation, Polars for data frames, Pandera v3 for DataFrame schemas, asyncpg and SQLAlchemy 2 async for the database. The ML stack centres on MLflow 2.x for tracking and registry, the Nixtla suite for time-series forecasting, scikit-learn and gradient-boosted tree libraries for classical ML, PyTorch for deep learning, and Optuna for hyperparameter search. The frontend uses React 19 with Vite, TanStack Query and Router, and shadcn/ui on Tailwind v4. Infrastructure runs on Cloud Run, Cloud SQL, GCS, Secret Manager, and Artifact Registry, provisioned by Terraform and delivered by GitHub Actions with Workload Identity Federation.

## What this document is not

- It is not a product specification. Feature definitions belong in product documentation, not in architecture.
- It is not a timeline. Build sequence is described by prerequisites and acceptance conditions; calendar estimates are omitted because the implementor is agentic and because calendar estimates are the least durable part of any plan.
- It is not a security audit or compliance statement. It describes the posture that supports such audits.
- It is not a replacement for customer-specific engineering. Each customer brings integration requirements that require configuration and, occasionally, extension — the blueprint defines the seams, not the final product for every customer.

## How to read this document

The document is organised as a progression from principles to concrete mechanisms:

- The **Key Ideas** chapter elaborates the ten architectural bets listed above, with enough depth to make them defensible against "why not X?" questions.
- The **Design Brief** through **Roadmap** chapters describe the concrete mechanisms in depth: environment flavours, system and application architecture, tenancy, data and ML platforms, infrastructure, local development, CI/CD, observability, security, and build sequence.
- Technical readers evaluating a specific aspect of the platform can jump directly to the relevant chapter. Decision-makers can read this summary and the Key Ideas chapter and have sufficient grounding to evaluate the architecture as a whole.
