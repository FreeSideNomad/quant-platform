# Observability and Operations

## Principles

Observability is built on three pillars — structured logs, metrics, and traces — emitted by the same application code in every environment. The local docker-compose stack produces logs in the same JSON format as production; metrics are emitted against the same schema; traces follow the same propagation conventions. A developer can read production output and a local run side-by-side and compare them directly.

Every signal carries the tenant identifier as a label. In a silo topology, the tenant identifier is the project identifier, automatically attached by Cloud Logging and Cloud Monitoring. No application-level tenant injection is required for production signals; locally, a dev tenant label is set explicitly.

## Structured logging

The application emits every log event as a single-line JSON object with consistent fields:

- `timestamp` — ISO-8601 with microsecond precision
- `level` — `debug`, `info`, `warn`, `error`, `critical`
- `event` — the event name (e.g. `command.dispatched`, `projection.applied`, `training.submitted`, `inference.served`)
- `user_id`, `user_roles` — from the authenticated request context
- `request_id` — propagated from the inbound HTTP header or generated on ingress
- `trace_id`, `span_id` — from the OpenTelemetry context
- `duration_ms` — where meaningful
- `tenant_id` — for local and non-silo contexts; implicit at the project level in production

Free-text log lines are disallowed. Every log line carries structured data. Error logs always include the exception type, message, and stack trace in dedicated fields, not concatenated into a message string.

Cloud Logging parses the JSON format natively and indexes the top-level fields. Queries filter by `event`, `user_id`, `duration_ms`, or any combination. Saved queries (log-based metrics) are the primary alerting mechanism for application-level signals.

## Metrics

The application exposes an OpenTelemetry metrics endpoint scraped by Cloud Monitoring (via the OpenTelemetry Collector sidecar). Metrics fall into three tiers:

### Golden signals per endpoint

Every REST endpoint has automatic coverage for:

- **Request rate** (RED: Rate)
- **Error rate** (RED: Errors, by HTTP status and by exception type)
- **Latency distribution** (RED: Duration, histogram with p50, p95, p99)

These are derived from a single FastAPI middleware that observes every inbound request; no endpoint-specific instrumentation is required.

### Business metrics

Named counters and gauges tracking domain-level signals:

- Commands dispatched per type
- Events appended per aggregate type
- PGMQ queue depths
- Pipeline runs started, completed, failed (per layer, per source)
- Model training runs submitted, completed (per model, per status)
- Model inference requests (per model, per version)
- Model inference latency distribution
- Data quality violations per source

### Infrastructure metrics

Provided by Cloud Run, Cloud SQL, and GCS out of the box. The application does not re-emit these; it relies on GCP's native collection.

## Distributed tracing

The application is instrumented with OpenTelemetry. Every inbound HTTP request opens a root span; every outbound call (database query, PGMQ operation, GCS access, MLflow call) produces a child span. Trace context is propagated via W3C Trace Context headers.

Traces are exported to Cloud Trace. A request that touches the API, the event store, a PGMQ enqueue, a projector handler, a graph update, and an inference call produces a complete trace spanning all components — across the small set of single-purpose worker services (`api`, `worker-proj-*`, `worker-pipeline-*`, `worker-training`, `worker-inference-batch`, `scheduler`) all sharing the same database, which means traces are usually short, the inter-service hops are few, and the topology is easy to reason about.

Cross-service traces (application -> MLflow -> back) include the MLflow service's spans, enabling end-to-end latency analysis of model serving paths.

## Dashboards

Two dashboard tiers exist:

### Per-tenant dashboards

A Cloud Monitoring dashboard scoped to each tenant's project. Contents:

- **Service health** — Cloud Run request rate, error rate, latency; Cloud SQL CPU, memory, connections
- **Queue health** — PGMQ queue depths, consumer lag, DLQ accumulation
- **Pipeline health** — daily pipeline run success rate, row counts, data quality score trends
- **Model health** — training success rate, inference latency per model, inference error rate
- **Business activity** — active users, commands per minute, unique models served

Enterprise-tier customers have IAM read access to their own dashboards; they can see the same view the vendor oncall sees.

### Fleet dashboards

In the platform project, Cloud Monitoring scoping projects aggregate signals across all tenants. Contents:

- Tenant count by version
- Fleet-wide error rate trend
- Worst-performing tenants by latency or error rate
- Upcoming maintenance windows
- Capacity planning signals (storage growth, database size trends)

Fleet dashboards are accessible only to the vendor operations team.

## Alerting

Alerts are configured in Cloud Monitoring with two severity levels:

**Page** (wakes someone up):
- Application error rate above threshold for five minutes
- Database unavailable for two minutes
- Queue depth above critical threshold for thirty minutes
- Training job failures above threshold for one hour
- Authentication failures above threshold for five minutes (potential brute force)

**Ticket** (creates a work item):
- Data quality score below threshold for a day
- Storage growth projecting against quota within thirty days
- Backup verification failure
- Version drift across fleet beyond policy

Every alert has a linked runbook in the repository's `docs/runbooks/` directory. Runbooks follow a strict template: symptom, immediate mitigation, investigation steps, resolution, and post-incident actions.

## Audit trail

In addition to operational logs, the platform maintains an application-level audit trail for security- and compliance-relevant events:

- User login and logout
- Role assignment changes
- Model promotion and demotion
- Training data extraction (including the extracted `as_of` timestamp)
- Inference requests (in the `inference_log` table)
- Administrative configuration changes

The audit trail is append-only, stored in a dedicated Postgres table with cryptographic chaining (each row includes the hash of the previous row's content, detecting tampering). For regulated customers, the audit trail is exported nightly to a WORM GCS bucket with Object Lifecycle Lock.

## Incident response

Each tenant incident follows a standard response:

1. **Detection** — an alert fires or a customer reports an issue
2. **Triage** — the oncall engineer identifies the affected tenant (from alert labels) and classifies severity
3. **Mitigation** — follow the runbook for the alert; the first action is usually traffic rollback to the last-known-good revision
4. **Investigation** — structured logs, traces, and the control plane's deployment history provide the full context
5. **Resolution** — deploy a fix through the normal pipeline; emergency fixes follow an expedited review but never skip the PR and staging gates
6. **Postmortem** — every customer-impacting incident produces a postmortem document, reviewed internally and (for significant incidents) shared with the affected customer

The postmortem template is structured and blameless. Its outputs feed the engineering backlog and the runbook library.

## Operational cadence

The operations team runs a weekly fleet review that walks through:

- Incidents in the preceding week (severity, tenant, root cause, resolution)
- Version drift status across the fleet
- Upcoming maintenance windows and planned changes
- Top five tenants by support burden
- Top five tenants by resource consumption
- Backlog of pending tenant onboardings and offboardings

The review drives tactical prioritisation and surfaces systemic issues that merit engineering investment (e.g. a recurring class of incident that a platform change could eliminate).
