# Key Ideas

This chapter elaborates the ten architectural bets named in the executive summary. Each section opens with **what the customer gets** from the bet, then explains the engineering choice that delivers it, the rejected alternative, and the condition under which the decision should be revisited.

The customer-value framing is deliberate. Architectural bets are interesting to engineers; customer outcomes are interesting to buyers. The bets are the *means*; the outcomes are the *ends*. This chapter inverts the usual order so that a non-engineering reader can follow the chapter without losing the thread.

For the customer-facing positioning these outcomes serve, see `blueprint/positioning/2026-04-21-positioning.md`. For how this architecture compares to credible alternatives (SigTech, Domino, Palantir Foundry, Databricks, build-your-own), see Chapter 14.5.

## 1. Silo tenancy — infrastructure is the isolation boundary

**What the customer gets:** Their data and their proprietary code never co-reside with another customer's. For hedge funds whose security teams have rejected multi-tenant SaaS for production-grade workloads, this is the difference between *can deploy* and *cannot deploy*. For LP allocators whose operational due-diligence questionnaires ask about tenancy isolation and data residency, this is a structurally clean answer. For separately-managed-account (SMA) mandates that contractually require per-mandate isolation, it is a deployment shape that fits the legal contract directly.

**What we built:** Every customer receives a dedicated GCP project containing a dedicated Cloud Run service set, Cloud SQL instance, GCS buckets, and Secret Manager namespace. There is no shared database, no shared application process, no row-level security policy. Tenant separation is achieved by separate deployments, not by runtime filters inside shared infrastructure. Optional Bring-Your-Own-Cloud (BYOC) deployment puts the entire tenant project in the customer's own GCP organisation, with the vendor holding limited-scope deployment access only.

**Alternative considered.** Pool tenancy with row-level security and a `tenant_id` column on every table is operationally cheaper at low customer count and universally recommended for consumer SaaS. It is the wrong choice here because hedge funds pay for isolation, demand it in security reviews, and sometimes insist that their infrastructure live in their own cloud account. Pool tenancy cannot deliver those properties. SigTech, Domino, and most generic MLOps platforms chose pool; the differentiation case for our platform begins here.

**What it costs us.** Materially simpler application code (no middleware injecting tenant context, no RLS policies, no noisy-neighbour reasoning) at the cost of a higher per-tenant infrastructure floor and a control plane that must manage a fleet. The control plane is the price of silo; it is a price worth paying for this market segment.

**Scope of isolation.** The silo isolation operates at the GCP-project / deployment layer (one project per tenant; one Cloud SQL instance per tenant). The application code does NOT carry a `tenant_id` column or scoped queries — it assumes its database serves exactly one tenant. The architecture forbids two tenants from sharing a database; if that constraint were ever violated (e.g., a misconfigured BYOC deployment), data would be co-mingled because the code layer has no tenancy guard. Production deployment must enforce one-tenant-per-database at the infrastructure layer.

**Revisit when:** the platform targets a market tier for which silo economics do not hold (sub-thousand-dollar monthly pricing, for instance). Pool tenancy can coexist with silo tenancy within a single codebase, but it doubles the test matrix and is not free.

## 2. Local-first development — full production simulation of the *workflow* on a laptop

**What the customer gets:** A new quant hire is productive in week one, not month three. A researcher iterating on a feature does not wait for cloud round-trips during the inner development loop. A bug surfacing in production can be reproduced on the engineer's laptop within minutes. The "works on my machine" / "fails in CI" / "fails in production" divergence — the bane of mid-sized engineering teams — is structurally eliminated.

**The honest scope.** Local-first means the **development workflow** is fully reproducible on a laptop, not that production-scale **training compute** runs there. The distinction matters and is sometimes missed:

- **Reproducible locally:** the OIDC authentication flow, the data ingestion pipelines (against scaled-down sample data), the CQRS event loop, the model-training entrypoint (with a small dataset and a small model), the inference serving path, the audit trail mechanics, the integration test suite. The behaviours, not the scales.
- **Not reproducible locally:** training a Transformer on multi-year Alpha360 data, hyperparameter sweeps across hundreds of configurations, GPU-bound deep-learning jobs, multi-day backtest sweeps. These run on managed cloud compute (Cloud Run Jobs for CPU, Vertex AI Custom Training for GPU) by design. The developer launches them with one command from the local environment; the *job* runs in the cloud.

The slogan is *"the same code path runs locally and in the cloud, validated end-to-end"*, not *"production runs on your laptop"*. A team writing pipeline logic against the local docker-compose stack has high confidence that the same logic runs in production; that is the value. They do not (and should not) train a production Transformer on a MacBook.

**What we built:** A docker-compose stack with Postgres (all extensions), MinIO (GCS substitute), MLflow tracking, and a mock OIDC provider. The application code uses environment variables to select between local and production backends; the major Python libraries in the stack respect well-known emulator conventions (`STORAGE_EMULATOR_HOST`, `MLFLOW_TRACKING_URI`, etc.). Cloud-only services that cannot be simulated locally are disqualified from the architecture. The CI pipeline runs the same docker-compose stack the developers run locally; "works on my machine" diverges from "works in CI" only on resource constraints, not on behavioural differences.

This constraint has shaped multiple downstream choices. Cloud Workflows has no emulator, so orchestration is done with Python state machines. Cloud Tasks has no emulator, so queueing is done with PGMQ. Cloud Scheduler has no emulator, so in-application APScheduler does the job. Identity Platform is rejected in favour of direct OIDC federation because the blocking-function model fragments code across Cloud Functions.

**Alternative considered.** Cloud-tethered development (the Databricks / SigTech / Domino model) where the researcher works against a hosted environment from day one. Faster onboarding to a *running* environment; slower inner-loop iteration; harder to debug; harder to test changes; harder to develop offline. The trade-off favours local-first for our segment.

**Revisit when:** never. This is the governing constraint for the development workflow.

## 3. Single image, multiple roles

**What the customer gets:** One codebase to reason about, one test suite to maintain, one image to scan for vulnerabilities, one CI/CD flow to operate — but with the runtime independence of microservices. A worker pool can scale on queue depth without affecting the API; a misbehaving worker cannot starve the API of event-loop time; release cadence is per-codebase, not per-service. The customer's engineering team operates a small fleet of single-purpose services without paying the operational overhead of a microservice sprawl.

**What we built:** One Docker image is built from one codebase and deployed as many services, each running a different role. Roles include: the API server, each projector worker, each pipeline worker, the training orchestrator, the batch inference worker, and the scheduler daemon. At container startup, a single environment variable selects which role the process plays; the rest of the image is identical.

This is distinct from two patterns sometimes conflated with it and both rejected:

**Scattered serverless** — one Cloud Function or Cloud Run service per task, typically with its own repository or its own CI/CD pipeline. This fragments the codebase, multiplies operational surface area, breaks local testability, and loses the transactional guarantees that come from a shared database client. A team running thirty such services is slower to diagnose, slower to refactor, and more prone to version-skew bugs than a team running one codebase.

**Single-process kitchen sink** — one `uvicorn` process hosting the API plus every worker type as asyncio tasks. This is simpler for a toy prototype but fails in production: workers cannot scale independently of the API, a misbehaving worker can starve the API of event-loop time, and queue backlog pressure cannot drive additional worker capacity because there is no worker capacity to add. The single-process pattern is rejected on the same grounds as scattered serverless: it sacrifices the runtime independence that distinguishes a production worker pool from a prototype.

The single-image-many-roles pattern avoids both failure modes. Workers must autoscale on queue depth, not just on CPU. A graph projector pool with ten thousand pending messages must scale out even if individual worker CPU is low. A pool with a drained queue must scale back in to zero or one replica. The infrastructure chapter describes the three mechanisms by which this queue-depth autoscaling is implemented on GCP.

**Revisit when:** per-role release cadences diverge enough that the API and the workers can no longer share a build train, or one role's dependency footprint must shrink dramatically (typically for cold-start reasons) and cannot do so within a shared image. The specific per-role deployment target (Cloud Run versus GKE) may evolve based on scaling requirements; the single-image-many-roles property is stable across either choice.

## 4. Postgres as the operational substrate

**What the customer gets:** Transactional coherence across event store, aggregate state, message queue, graph store, time-series store, scheduler, and audit log. The "transactional outbox" pattern — a recurring source of subtle distributed-systems bugs — simply ceases to exist as a problem because the queue lives in the same database as the state changes it announces. For the customer's compliance team, the audit log is *queryable in the same database* as the operational state; for the customer's quant team, a command handler that updates aggregate state and enqueues projection messages does so in one transaction that either commits or fails atomically.

**What we built:** A single Postgres database — Cloud SQL by default, AlloyDB where required — holds the event store, the aggregate state, the message queue (PGMQ), the graph store (Apache AGE), the time-series store (TimescaleDB), the scheduler (pg_cron), the user registry, the audit log, and the read models. Blob storage in GCS holds raw files and model artefacts; everything else is in Postgres.

The driving insight is that most architectural services the industry typically implements as separate products — Kafka for queueing, Neo4j for graphs, Kdb or InfluxDB for time series, Redis for caching — have first-class Postgres extensions that cover the same ground at a scale many times larger than the target customer's workload. Treating Postgres as the platform eliminates cross-system consistency problems, collapses the operational surface, and makes everything transactionally coherent.

**Alternative considered.** Multi-store architectures (Kafka + Postgres + Neo4j + Kdb + Redis) are the default in the modern data-platform world, particularly at the petabyte scale Databricks targets. They are over-engineered for a customer whose operational data fits comfortably in Postgres (which is essentially every quant shop with under $20B AUM) and they multiply the failure domains. We deliberately chose simpler.

**Revisit when:** a specific extension hits a fundamental ceiling. PGMQ handles tens of thousands of messages per second on commodity hardware (per Tembo's published PGMQ benchmarks); beyond that, a dedicated broker (Kafka) may be required. AGE's traversal planner is fine for shallow-graph queries; deep graph analytics at scale may demand Neo4j. TimescaleDB covers most time-series needs; tick-level HFT data may demand Kdb. None of these conditions apply to the target customer segment today.

## 5. Command-Query Responsibility Segregation

**What the customer gets:** A complete, replayable history of every state change, queryable forever. The compliance officer can answer "what did the system know at 4pm on the trade date" by replaying the event log. The quant lead debugging an unexpected inference output can trace it back through every command that produced it. The LP auditor asking "show me how this strategy's positions evolved over the past month" sees an answer derived from immutable events, not from interpreted state. CQRS sounds like an engineering pattern; for the customer it is the substrate that makes audit, reproducibility, and time-travel queries possible at all.

**What we built:** Writes go through aggregates that emit versioned events. Reads come from purpose-built projections, each populated by a projector that consumes events from a PGMQ queue. The event log is the source of truth; everything else is derived.

CQRS is sometimes seen as a complexity burden imposed on simple systems. The choice here is deliberate and contextual. Hedge-fund workloads are audit-heavy, regulator-visible, and demand point-in-time reconstruction of past states — exactly the conditions where the event log becomes load-bearing.

The specific CQRS shape chosen has three properties worth noting. First, events are persisted in the same Postgres as aggregate state, enabling the single-transaction guarantee described in §4. Second, each projector role runs as a dedicated worker service stamped from the same image, with internal concurrency implemented via asyncio tasks within that worker; projector workers are not co-resident with the API process but share its codebase, test suite, and build pipeline. Third, every projector is idempotent by construction, keyed on `event_id`; rebuilding a projection is a matter of truncating its state table and replaying the event log.

**Revisit when:** a specific workload does not benefit from the event-sourced model — a short-lived internal tool, a pure analytics dashboard. CQRS is the default for the customer-facing platform, not a universal rule.

## 6. Medallion data platform, file-first

**What the customer gets:** The platform's data ingestion shape *fits* the actual integration reality of hedge-fund customers, who exchange files with vendors, prime brokers, custodians, and fund administrators rather than streaming events. A data engineer at a customer integrating a new vendor does not have to convince that vendor to build a streaming integration; they configure a file pattern. Streaming, where it exists, is treated as a special case of micro-batched files, which means the rest of the data platform's machinery applies uniformly.

The other gift to the customer is **point-in-time correctness as a schema property**: every silver and gold row carries a `_knowable_at` column (system time — when the datum became visible to the platform) alongside `_valid_from` and `_valid_to` columns (the business-time interval over which the datum applies). Training-data extraction queries without a `_knowable_at` filter fail validation at pipeline-build time; bi-temporal reconstructions ("what did we believe on date T about period P?") combine both halves. The data platform chapter documents the four columns in full. This is the discipline that prevents look-ahead bias from being a researcher discretionary practice and makes it instead a structural property.

**What we built:** Inbound data arrives as files. Outbound data leaves as files. Between them, three layers of progressively more curated data live in GCS (bronze, immutable parquet) and Postgres (silver and gold, typed and aggregated). Every bronze file is identified by content hash. Every silver row carries lineage to its bronze source. Every gold aggregate is reproducible from silver by re-running a pure function.

The medallion layers are wrapped in Dagster's software-defined-asset model: bronze, silver, and gold tables are assets, dependencies between them are the asset graph, and data-quality rules are asset checks attached to the asset they validate. The customer's quant lead sees the lineage of any gold aggregate back to its bronze sources in one screen; the customer's compliance officer sees data-quality breaches at the same place they see the asset itself; the LP allocator running operational due diligence sees concrete evidence that gold-layer outputs trace cleanly back to vendor files with no off-graph manual steps. APScheduler triggers materialization runs on cadence, PGMQ carries the event-driven materialization triggers, and Dagster owns the asset graph; the three coexist rather than compete.

**Alternative considered.** Streaming-first / event-driven data platforms are the default in cloud-native architectures (Kafka → Flink → object store). They are well-suited to ad-tech, IoT, and real-time analytics workloads. For hedge-fund integrations they are over-engineered: vendors send files, regulators expect file evidence, audit requires file provenance. Designing the platform around file exchange and treating streaming as a file-micro-batching special case yields a system that fits its integration surface.

**Revisit when:** a specific customer's workload is genuinely streaming-first (market-making, sub-second signal generation). Extend the platform to run streaming as the first-class path for that customer, not the other way round.

## 7. Research-to-production code parity

**What the customer gets:** The single most expensive class of bug at quant shops — the feature that worked in the research notebook but produces different numbers in production — ceases to exist as a class. The quant who finishes a research piece does not hand off to engineering for re-implementation; the research code *is* the production code. Train-serve skew is closed at the platform level, not left to team discipline.

**What we built:** The Python function that computes features at training time is the same function that computes features at serving time. It is packaged into the MLflow `pyfunc` artefact alongside the trained model, so that the model and its preprocessing travel as one unit. Researchers import the same function when prototyping; the notebook becomes a draft of the production serving path, not a parallel artefact that will later be re-implemented.

This addresses the second-largest class of quantitative-strategy failures, after look-ahead bias: code divergence between research and production. A feature computed one way in the notebook and a different way in production silently breaks the model. It is a class of error that quantitative teams rediscover repeatedly, and the only reliable fix is to make the code identical by construction.

The `pyfunc` wrapper is the vehicle. It captures both the trained weights and the inference code. Upgrading a model cannot break the serving endpoint's calling contract, because the endpoint calls the wrapper, not a hand-written preprocessor.

**Revisit when:** the model registry's `pyfunc` packaging convention ceases to be the standard vehicle for the libraries the platform depends on, or a customer's preferred framework cannot be wrapped without losing the parity guarantee. Legacy models without `pyfunc` wrappers may ship through a different path during migration; the target is zero such models in steady state.

## 8. Point-in-time correctness as a platform property

**What the customer gets:** Backtests that survive their own promotion to production. A model trained on data filtered by `_knowable_at <= :as_of` is trained on a counterfactual the manager could have actually constructed at the simulated decision time; the alpha that shows in backtest is alpha that would have been available in production. For an LP allocator running ODD, a manager whose platform enforces this discipline as a query-time gate (not a researcher's optional practice) is a manager with a structurally honest backtest pipeline.

**What we built:** The platform maintains both system-time and valid-time on silver and gold rows: a `_knowable_at` column records when the datum first became visible to the platform; `_valid_from` and `_valid_to` record the business-time interval over which the datum applies. Both are distinct from the original business-event timestamp. Queries that extract training data must filter by `_knowable_at <= :as_of`; queries without this filter fail pipeline validation before they ever run. Temporal queries that ask "what did we believe at time T about period P?" combine the two: filter `_knowable_at <= T` and intersect with valid-time on P.

This is the primary defence against look-ahead bias, which the quantitative-finance literature consistently identifies as a leading cause of strategies that appear profitable in backtests and fail in production (López de Prado, *Advances in Financial Machine Learning*, Wiley 2018, Ch. 11–13; Bailey & López de Prado, "The Probability of Backtest Overfitting," *Journal of Computational Finance*, 2014). The typical scenario is innocuous-looking: a consumer credit-card transaction dated Monday is aggregated by the vendor on Wednesday and arrives at the customer on Thursday. Using Thursday's file to backtest decisions as of Monday introduces days of hindsight into the simulation and produces spurious profits.

Bi-temporal data models are well understood in the academic literature and in specialist financial-data vendors' products. They are rarer in general-purpose data platforms, because they add modelling overhead. The blueprint takes the overhead as non-negotiable for the target market.

**Revisit when:** an as-yet-unforeseen workload demonstrates that the bi-temporal modelling overhead exceeds its benefit — none anticipated for the target customer segment.

## 9. Blue/green deployment via Cloud Run revisions

**What the customer gets:** Releases that ship without downtime, with a one-command rollback path. The customer's quant lead can promote a new model on a Friday afternoon, have it serve a fraction of traffic for the weekend, and either roll out or roll back on Monday based on observed metrics — without any of this requiring engineering intervention. For the customer's compliance team, every release is a discrete event with its own audit trail entry; a "what changed when" question has a structured answer.

**What we built:** Every release is a new Cloud Run revision. Traffic to the new revision starts at zero and shifts in configured increments with health checks between each step. The previous revision is retained for a configured window to allow immediate rollback via a single traffic-configuration change.

Cloud Run's native revision model is the blue/green primitive. There is no need for a separate blue/green system, no need for traffic-management infrastructure, no need for container orchestration outside what Cloud Run provides. The rollback path is a command, not a rebuild.

The property that makes this safe is forward-compatible schema migrations. The new revision must work with both the old schema (before migration) and the new schema (after migration). The expand-migrate-contract pattern enforces this: add columns and tables (safe for both versions), deploy new code that uses them, backfill as needed, remove the old structures in a later release. This adds a release cycle to every schema change but eliminates a class of downtime incidents.

**Revisit when:** a specific release requires a breaking change that cannot be made forward-compatible. Such releases are rare and should be planned carefully — typically across multiple quieter releases — rather than forced into one deployment.

## 10. Control plane as an internal product

**What the customer gets:** Indirectly, what the customer gets from the control plane is *operational reliability of the silo tenancy model itself*. A vendor without a control plane manages a fleet of silo tenants by hand; the per-tenant operational mistakes compound; eventually the customer notices that an upgrade landed late, a backup didn't run, a maintenance window was missed. The control plane is the price the vendor pays so that silo tenancy remains operationally credible at scale.

For the user (vendor operator), the control plane is the tool that makes managing fifty tenants feel like managing one. Provisioning, upgrading, monitoring, and billing are all driven through it.

**What we built:** The control plane is a separate application, run by the vendor's operations team, that manages the fleet of tenant instances. It knows every tenant, their current version, their maintenance window, their contract tier. It orchestrates provisioning (Terraform apply), upgrades (wave-based rollouts), and fleet telemetry. Customers never see the control plane.

The existence of a control plane is the operational consequence of silo tenancy. A single-tenant SaaS business has no use for a control plane; a hundred-tenant silo SaaS business lives or dies by the quality of its control plane. Treating it as a first-class product — with its own release cadence, observability, and success metrics — is what makes silo economics work at scale.

The control plane shares the repository and CI/CD pipeline of the main application, because the two products evolve together: a new application feature that requires a new Secret Manager entry must be reflected in the provisioning flow for new tenants. Decoupling the repositories would mean every application change requires a matching control-plane change in a separate PR, which is friction without benefit.

**Revisit when:** the control plane's complexity outgrows the team's ability to evolve it in-line with application changes. Splitting it out then is a deliberate graduation, not an early optimisation.

## Summary

The ten bets are mutually reinforcing. Silo tenancy demands a control plane; local-first constrains technology choices; Postgres-centric design enables transactional CQRS; CQRS plus bi-temporal data delivers point-in-time correctness; file-first medallion data matches the customer's integration reality; code parity plus the registry eliminate train-serve skew; Cloud Run revisions plus forward-compatible migrations deliver safe continuous delivery; customer IdP federation keeps the platform out of the user-store business.

Read in customer-value terms: silo + BYOC says *your data and code stay in your cloud*; local-first says *your developers iterate on a laptop, not a Databricks workspace*; single-image-multi-role + CQRS + Postgres-centric say *your operations team manages a small comprehensible fleet, not a distributed-systems Rube Goldberg*; medallion + bi-temporal say *your backtests are honest by construction*; research-to-production parity says *your quants ship without an engineering hand-off*; blue/green + control plane say *your platform stays available and evolves under wave-based releases without your team owning that orchestration*.

The detailed chapters that follow describe how each of these ideas is implemented concretely. Chapter 14.5 compares this architecture explicitly to the credible alternatives.
