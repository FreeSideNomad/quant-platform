# Data Platform

## Medallion architecture

The data platform follows the medallion pattern: incoming data lands in a raw **bronze** layer, is cleaned and typed into a **silver** layer, and is aggregated into a **gold** layer that serves the application's read models, the training pipelines, and downstream analytics.

![Medallion data flow](diagrams/rendered/05-medallion-flow.pdf){width=95%}

### Bronze

Raw data as received, stored in object storage (GCS in production, MinIO locally) as immutable parquet files. The storage path encodes tenant (implicit — the bucket is per-tenant), source system, ingestion date, and a content hash:

```
gs://{tenant-bucket}/bronze/{source}/{yyyy}/{mm}/{dd}/{file_hash}.parquet
```

Files are never overwritten. A re-delivery from the source produces a new file with a new hash. File lifecycle is managed by bucket lifecycle rules — Nearline at thirty days, Coldline at ninety days, deletion at the configured regulatory retention horizon (typically seven years for hedge-fund workloads).

A `bronze_files` table in Postgres records every arrival: tenant, source, URI, hash, received time, size, and processing status. This table is the authoritative inventory of ingested data and is the basis for incremental processing.

Accepted on-the-wire formats include CSV, JSON, and parquet. Non-parquet inputs are converted to parquet on arrival and the original format is preserved alongside for replay.

### Silver

Cleaned, typed, and validated data held in Postgres tables, partitioned or hypertable-organised for time-series sources. Silver is the operational source of truth for all downstream consumption.

Each silver table carries lineage columns — `_bronze_uri`, `_bronze_hash`, `_ingested_at` — linking every row back to the raw file it came from. Data quality validation is performed in-flight: a row that fails validation is routed to a `quarantine` table with a reason code, never silently dropped.

Silver transformations are implemented as Python functions using Polars (preferred) or pandas (for legacy libraries). Each function is independently testable, idempotent (upsert by natural key), and exposed as a Dagster software-defined asset whose materialization is triggered either by APScheduler on a cron cadence or by a PGMQ message emitted on bronze arrival.

A `ingestion_watermark` table records per-source processing progress — `(source, last_processed_hash, last_processed_at)` — to support incremental loads without reprocessing.

### Gold

Business-level aggregates served by Postgres tables, materialised views, or TimescaleDB continuous aggregates. Gold is shaped by consumer: a read model for the UI, a feature set for model training, an analytical view for internal reporting.

Gold tables emit domain events on update. The event flows to the CQRS event store and to any projection subscribed to gold-layer changes. This closes the loop between the data platform and the application: pipeline outputs become first-class events that drive read models and trigger downstream actions (retraining, alerting, compliance checks).

## File-based ingestion and output

The realistic operating mode for hedge-fund customers is file-based. Data vendors deliver files. Prime brokers send files. Custodians publish files. Fund administrators receive files. The platform accordingly treats file exchange as the primary integration surface, with streaming treated as a specialised case rather than the default.

### Inbound ingestion patterns

The platform supports four inbound patterns, each covering a different category of source:

**Scheduled pull** — the platform reaches out to the source on a cron cadence and retrieves new files. Applicable to SFTP servers, HTTPS endpoints returning file listings, and vendor APIs that support "list since timestamp" semantics. APScheduler triggers a pull job that authenticates (using credentials from Secret Manager), enumerates new files, downloads them, computes their content hashes, and writes them to the bronze bucket. Idempotency is enforced by content hash: a file whose hash is already in the `bronze_files` registry is skipped.

**Push drop to GCS** — the source uploads directly into the tenant's GCS bucket. This is the cleanest mechanism when the source supports it (most modern data vendors do). A GCS object-notification trigger emits an event that is received by a small webhook endpoint on the application, which enqueues a bronze-processing message to PGMQ. No polling, no scheduler, minimum latency from arrival to processing.

**Push drop via SFTP to vendor landing** — for legacy sources that cannot reach GCS but can reach an SFTP server, the vendor writes to a shared SFTP landing operated by the vendor's own infrastructure. A scheduled pull job polls the SFTP landing and forwards new files into the customer's bronze bucket. This degrades gracefully to "scheduled pull" when direct GCS push is infeasible.

**Customer-operated drop** — the customer's own systems (trade booking, risk, compliance) write files directly into the tenant's bucket on their side of the integration. This is the pattern when the customer is sourcing their own data for their own models. The customer retains control of the production schedule and the delivery contract; the platform consumes what arrives.

Streaming ingestion is provided for sources that genuinely emit messages rather than files (market data multicast feeds, FIX execution messages). The streaming path is architecturally a special case of the file path: a persistent consumer micro-batches incoming messages into parquet files on short tumbling windows and writes them to bronze, after which the same silver-transformation code paths apply. This allows the rest of the platform to remain file-oriented regardless of the raw source shape.

### File contracts

Every source carries a versioned file contract that specifies:

- Expected file name pattern (with date tokens and sequence numbers)
- Expected format (CSV, parquet, or JSON; for CSV, delimiter, encoding, and header-presence options)
- Expected schema (column names, types, nullability, value domains)
- Expected delivery cadence (daily by 08:00 UTC, intraday every fifteen minutes, etc.) and tolerance windows
- Optional manifest file (a companion file listing expected content hashes, row counts, or checksums, allowing integrity verification before processing)
- Late-arrival policy (how far back corrections are accepted; how late deliveries are handled)

The file contract is machine-readable. The ingestion pipeline reads it, validates arrivals against it, and quarantines violations rather than attempting to muddle through. A CSV with an unexpected column is not silently mis-mapped; it is rejected with a specific reason code and surfaced to operations.

### Outbound delivery patterns

Model outputs, scheduled inference results, and exports flow out of the platform through an inverted set of the same patterns:

**Scheduled file export to customer GCS bucket** — the platform writes outputs to a customer-specified bucket on the customer's schedule. IAM on the customer's bucket grants the platform service account write access; no credentials are exchanged. The customer's downstream systems poll their own bucket and consume.

**Scheduled SFTP push** — for customers whose downstream systems cannot read from GCS, the platform uploads outputs to a customer-provided SFTP endpoint using credentials in Secret Manager. This path is explicitly supported, but discouraged; GCS-native delivery is preferred.

**On-demand signed URL download** — for ad-hoc or user-initiated exports, the platform writes the result to a short-lived location in its own bucket and returns a signed URL valid for a configured window (typically fifteen minutes to one hour). The user downloads directly from GCS; the platform never streams large payloads through its own API.

**API-returned batch results** — for small outputs (single-file inference results, score sheets, report summaries), the API returns the file content directly in the response. This path is available but bounded by a maximum response size; larger outputs are forced through signed URLs.

Every outbound delivery is recorded in an `outbound_deliveries` table with the target, the file URI, the content hash, the scheduled time, the actual delivery time, and the success status. The table is the audit record of what was sent to whom, queryable by the customer and by internal operations.

### Reconciliation and recovery

File-based integration produces a characteristic class of failure: the file never arrives, the file arrives malformed, the file arrives on time but with stale data, the file is duplicated. The platform handles each:

- **Expected-delivery monitoring** — the scheduler knows when each source is expected to deliver. If the tolerance window passes without arrival, an alert fires.
- **Content-hash deduplication** — the `bronze_files` registry prevents a re-delivered file from re-entering silver; the row count tells operations that a duplicate was detected.
- **Manifest verification** — where manifests are provided, mismatch triggers quarantine and an operations alert before downstream processing.
- **Row-count reconciliation** — silver-to-gold loads emit row-count deltas; anomalies (a drop of 90% from yesterday) page operations before contaminated data reaches model training or serving.
- **Backfill and replay** — the `bronze_files` registry supports re-emission of bronze-ingested messages for a specified date range, causing the full silver-and-gold pipeline to re-execute. This is the recovery mechanism when a source publishes corrections for past dates.

## Transformation and validation

Transformations are plain Python functions organised under `app/pipeline/`, grouped by layer (`bronze_to_silver`, `silver_to_gold`) and by domain (`positions`, `prices`, `trades`, `reference_data`). Each function has a single responsibility, a typed input and output, and a matching unit test.

Validation uses Pandera (preferred for Polars/pandas DataFrames) or pydantic (for row-level validation of smaller datasets). Every silver-layer load applies the source's validation schema; failures are routed to `quarantine` rather than failing the pipeline outright.

Data quality metrics — row counts, null rates, distribution shifts — are emitted as observability signals at the end of every pipeline run. Thresholds are per-source and per-tenant; breaches trigger alerts without blocking the pipeline (except for critical sources where block-on-violation is explicitly configured).

## Scheduling and orchestration

Three components share the orchestration surface, each handling a different concern:

- **PGMQ** carries the CQRS command-and-event flow. It lives in the same Postgres instance as the aggregate state it announces, so a command handler can update state and enqueue projection messages in one transaction. This is the substrate for the in-application event loop, not for the pipeline graph.
- **APScheduler** is the in-process cron. It triggers Dagster materialization runs on a cadence and handles the small set of recurring jobs (token refreshes, watermark sweeps, expected-delivery monitors) that do not warrant their own asset.
- **Dagster** is the data-and-ML pipeline orchestrator. Bronze, silver, and gold layers are modelled as software-defined assets; training runs and model versions are dynamic assets per strategy. Asset checks make data-quality enforcement first-class. Dagster's asset graph is the lineage view that quants, operations, and LP-allocator due-diligence reviewers all want to see.

The asset model fits the medallion architecture cleanly. Each silver transformation is an asset whose upstream is the bronze file (or files) it consumes; each gold aggregate is an asset whose upstream is the silver tables it reads. A row arriving in bronze does not have to be matched against a hand-maintained dependency table — the dependency *is* the asset graph, and Dagster materialises downstream assets in the correct order with the correct partitions. Asset checks attach validations (row counts, null rates, distribution tests) directly to the asset, so a data-quality breach surfaces in the same place as the asset's lineage and run history.

The end-to-end flow for a typical bronze-to-gold path:

1. A bronze file arrives (via scheduled pull or push drop) and a `bronze_ingested` message lands on PGMQ.
2. A small worker consumes the message and triggers materialization of the corresponding silver asset in Dagster (for event-driven sources) or APScheduler triggers a periodic materialization of a window of silver assets (for cron-driven sources).
3. Dagster materialises the silver asset, runs its asset checks, and propagates the materialization to downstream gold assets according to the asset graph.
4. Gold materialization emits a `gold_updated` domain event back onto PGMQ, which projectors, training triggers, and alerting rules subscribe to.

The Dagster UI is exposed read-only to operators and to quants through the BFF on the `/dagster/*` proxy path. The same UI surfaces the visual DAG, partition status, asset-check results, and run history. For an LP allocator running operational due diligence, the lineage view is concrete evidence that gold-layer aggregates trace cleanly back to bronze files with no off-graph manual steps.

Run storage uses the existing Postgres instance — Dagster does not introduce a new database. In local development Dagster is a docker-compose service on port 3000; in production it is a Cloud Run service in the tenant project. Backfills are first-class Dagster operations, invokable from the UI or from a CLI; the previously CLI-only backfill path is retained for headless and scripted use.

The argument for Dagster as a v1 component (rather than the deferred component it was in earlier drafts) is the lineage UI and the asset-check model. APScheduler plus PGMQ alone can drive the pipeline; what they cannot do is *show* the pipeline. The asset graph is the visual artefact a non-engineering reviewer can read, and the asset checks are the structural place to encode data-quality rules. Both are shippable as part of the v1 demo without new infrastructure.

Airflow and Prefect were considered. Airflow's task-graph model is task-centric rather than asset-centric and a poorer fit for medallion data; Prefect is a credible alternative, but Dagster's asset checks and lineage UI are decisive for this market segment.

## Point-in-time correctness

Quantitative workloads demand point-in-time correctness — a model training run must see the data as it was known on the training date, not as it has been subsequently corrected. The platform enforces this with a bi-temporal schema that captures **both** halves of the bi-temporal model on every silver and gold row:

- `_knowable_at` — system time. The timestamp at which the datum first became visible to the platform (typically the bronze-landing time of the file that carried it). This is the column training-extraction queries filter on.
- `_valid_from` / `_valid_to` — valid time. The business-time interval over which the datum applies. Corrections replace the interval rather than overwrite the row.
- The original business-event timestamp on the underlying fact remains in its own column (e.g. `trade_date`, `observation_date`), untouched by the bi-temporal columns above.

Training pipelines always specify an `as_of` timestamp and filter `_knowable_at <= :as_of`. Extraction queries that lack this filter fail pipeline validation before they can ship. Bi-temporal reconstructions ("what did we believe on date T about observations over period P?") combine the two halves: filter `_knowable_at <= T` and intersect with the valid-time interval covering P.

Corrections to historical data create new rows rather than updating old ones. The old row's `_valid_to` is set to the correction's effective time; the new row's `_valid_from` matches, and its `_knowable_at` reflects when the correction itself became visible. This allows the platform to answer both "what did we know at time T?" (system time, for training reproducibility) and "what was true for period P as currently understood?" (valid time, for reporting).

TimescaleDB's support for this pattern via hypertable constraints and continuous aggregates on time-bounded ranges is one of the reasons for its inclusion in the default stack.
