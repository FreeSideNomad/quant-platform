# Infrastructure

## Per-tenant resource topology

A single customer instance consists of a dedicated GCP project containing the resources shown below. Every resource is provisioned and managed by a Terraform module, applied as a unit per tenant.

![Per-tenant infrastructure layout](diagrams/rendered/07-tenant-infra.pdf){width=95%}

| Resource | Purpose |
| :--- | :--- |
| GCP project | Tenant isolation boundary, billing boundary, IAM boundary |
| Cloud Run service (`api`) | The API role of the application image |
| Cloud Run services (`worker-*`) | One Cloud Run service per worker role, each stamped from the same image with a different `ROLE` env var |
| Cloud Run service (`scheduler`) | APScheduler daemon, single replica (min=1 max=1) |
| Cloud Run service (mlflow) | MLflow tracking server (separate image) |
| Cloud SQL (default) or AlloyDB (where required) instance | Postgres with AGE, TimescaleDB, PGMQ, pg_cron extensions. Cloud SQL is the default; AlloyDB is selected only when a required extension is unavailable on Cloud SQL in the deployment region. See Architecture chapter §Container view for the rule |
| GCS bucket (data) | Bronze layer files, exported datasets, scheduled inference outputs |
| GCS bucket (artefacts) | MLflow model artefacts, training checkpoints |
| GCS bucket (frontend) | Optional: React SPA assets for CDN delivery |
| Artifact Registry | Pulls only; images are pushed from the vendor's shared registry |
| Secret Manager entries | IdP configuration, session JWT signing key, data source credentials |
| Cloud Load Balancing | Custom domain termination, SSL, Cloud CDN for frontend |
| VPC Service Controls perimeter | Optional: additional egress controls for regulated tenants |

All application Cloud Run services run the **same image**. They differ only in their `ROLE` environment variable, their autoscaling policy, and their service account bindings. This is the single-image-multi-role pattern described in the application architecture chapter, realised at the infrastructure layer.

Billing is naturally attributed at the project level. Monitoring and logging scope to the project. IAM grants are scoped to the project's service accounts. Quotas are per-project.

## Worker autoscaling on queue depth

The defining operational property of the worker roles is that they must autoscale on PGMQ queue depth. A graph projector pool with a ten-thousand-message backlog must scale out even if individual workers have low CPU; the bottleneck is parallelism, not per-worker capacity. When the queue drains, the pool must scale back in to avoid paying for idle capacity.

Cloud Run's native autoscaling is driven by HTTP request rate, which is not a direct readout of queue depth. Three implementation options close this gap on GCP; the blueprint supports all three but defaults to the first.

### Option A: PGMQ-to-HTTP bridge (default)

A thin bridge process reads from PGMQ and issues an HTTP POST per message to the worker's Cloud Run endpoint, which processes the message and acknowledges. Cloud Run's request-rate autoscaling then behaves as it does for a Pub/Sub-push-backed Cloud Run service: requests come in, replicas scale up; requests stop, replicas scale down.

The bridge runs as its own role (`bridge-pgmq-http`) inside the same image, deployed as a small Cloud Run service with `min_instances=1` and modest concurrency. Its responsibility is narrow: drain PGMQ, post to the worker, handle HTTP errors by letting PGMQ's visibility timeout expire and retry.

This keeps everything on Cloud Run with no Kubernetes in the stack. It is the simplest option and the default in the Terraform module. The trade-off is one additional small service per queue; in practice a single bridge replica can drive many queues by multiplexing.

### Option B: KEDA on GKE Autopilot

For larger deployments where queue-depth autoscaling fidelity matters more than infrastructure simplicity, worker roles run on GKE Autopilot with KEDA (Kubernetes Event-Driven Autoscaling). KEDA has a native Postgres scaler that queries PGMQ's queue-depth view on a configurable interval and scales the deployment accordingly. Latency from queue depth to replica count is lower than Option A; the ceiling on replicas is higher.

The cost is a Kubernetes cluster to operate. GKE Autopilot removes most of the node-management overhead, but the mental model — pods, deployments, HPAs, service accounts with Workload Identity — is additional. This option is offered as a scaling path, not as the default.

### Option C: custom scaler modifying Cloud Run `min_instances`

A periodic job reads queue depth from PGMQ and calls `gcloud run services update` (or the REST API equivalent) to raise `min_instances` when backlog grows and lower it when backlog drains. Intermediate fidelity — not as responsive as KEDA, not as smooth as Option A, but keeps everything on Cloud Run and needs no additional service per queue.

Offered as an option for teams who find Option A's additional service unattractive but who do not want to introduce GKE. Rarely chosen in practice.

## Training and large-compute workloads

Training jobs — particularly GPU or multi-hour CPU jobs — do not fit the Cloud Run request-response model. They run as Cloud Run Jobs (for CPU, up to 24 hours) or as Vertex AI Custom Training (for GPU). Both are dispatched by the `worker-training` role and tracked asynchronously through PGMQ status-polling messages.

A Cloud Run Job is itself a Cloud Run resource stamped from the same image. The `ROLE` env var for a training job is `job-training`, and the job's entrypoint reads the training-run configuration from its launch arguments rather than from a queue.

## Cross-tenant resources

The vendor operates a small number of shared resources in a dedicated platform project:

- **Artifact Registry** — the single source for application container images. Each tenant's Cloud Run service pulls from this registry. Images are tagged by semantic version and by git commit SHA.
- **Control plane service** — the vendor's internal fleet-management application (see below).
- **Observability aggregator** — Cloud Logging and Cloud Monitoring scoping projects that aggregate signals across all tenant projects for vendor-side oncall.
- **GitHub Actions runners** — standard hosted runners, authenticated to tenant projects via Workload Identity Federation.

## The control plane

The control plane is the vendor's internal tool for managing the fleet of tenant instances. It is itself a small application — a FastAPI process with a Postgres database, deployed to Cloud Run in the platform project — and it is the operational nerve centre of the product.

### Responsibilities

- **Tenant registry** — the authoritative list of tenants, their configurations, their deployment topology (silo vs BYOC), their current application version, and their maintenance windows.
- **Provisioning orchestration** — triggering Terraform applies for new tenants, tracking the progress of provisioning steps, surfacing failures to the vendor's operations team.
- **Upgrade orchestration** — coordinating version rollouts across the fleet, respecting per-tenant maintenance windows and canary sequencing.
- **Per-tenant telemetry** — aggregated dashboards showing health, usage, and billing signals for each tenant.
- **Fleet telemetry** — cross-tenant views for capacity planning, error rate trends, and version sprawl tracking.
- **Customer contact and contract metadata** — for integration with support tooling, billing systems, and renewal workflows.

The control plane has no direct customer access. Customers interact with their own instance; the control plane is an internal product for the vendor's operations function.

### Silo vs BYOC

The control plane supports both tenancy deployment models:

**Silo (vendor-hosted):** the tenant GCP project lives in the vendor's GCP organisation. The vendor has full IAM access, operates the infrastructure, and bills the customer through the vendor's pricing plan. The control plane drives Terraform directly.

**BYOC (customer-hosted):** the tenant GCP project is owned by the customer. The customer grants the vendor a limited-scope service account with permissions to deploy Cloud Run revisions, read Cloud Monitoring metrics, and run Cloud Run Jobs for migrations. All data stays within the customer's cloud perimeter. The control plane drives Terraform through the customer-granted identity; certain operations (project creation, organisation-level policy changes) remain with the customer.

The Terraform module is identical across both models. Only the execution identity changes.

## Terraform module structure

A single root Terraform module provisions a tenant. Its inputs are tenant-specific: name, region, tier, IdP configuration, custom domain, data source credentials. Its outputs are the application URL, the MLflow URL, and the Cloud SQL connection string.

```
terraform/
├── modules/
│   ├── tenant/              # the root per-tenant module
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   ├── project.tf       # GCP project creation
│   │   ├── network.tf       # VPC, subnets, firewall
│   │   ├── database.tf      # Cloud SQL (default) or AlloyDB (where required); see Architecture §Container view
│   │   ├── app.tf           # Cloud Run services
│   │   ├── storage.tf       # GCS buckets
│   │   ├── iam.tf           # service accounts, IAM bindings
│   │   ├── secrets.tf       # Secret Manager entries
│   │   └── dns.tf           # custom domain, load balancer
│   ├── platform/            # shared platform resources
│   │   ├── artifact_registry.tf
│   │   ├── control_plane.tf
│   │   └── observability.tf
│   └── control_plane_db/
├── tenants/
│   └── {tenant-id}/
│       ├── terraform.tfvars # tenant-specific values
│       └── backend.tf       # remote state (GCS bucket in platform project)
└── platform/
    └── terraform.tfvars     # platform-wide configuration
```

Each tenant has its own Terraform state file in a GCS bucket in the platform project. The control plane invokes `terraform apply` with the appropriate working directory and state path when provisioning or upgrading a tenant.

## Secrets management

All secrets live in Secret Manager — one entry per secret, per tenant. Naming convention: `{tenant-id}/{secret-name}`. The application container reads secrets at startup via the application's service account, which has `roles/secretmanager.secretAccessor` scoped to the project.

Secrets include:

- **`idp-client-secret`** — the OAuth client secret for the customer's identity provider
- **`session-jwt-signing-key`** — the signing key for session JWTs (rotated quarterly)
- **`data-source-credentials/{source}`** — credentials for each configured data source
- **`database-password`** — Cloud SQL connection password (Cloud SQL IAM auth is preferred where supported, which eliminates this entry)

No secrets exist in container images, Terraform state files (marked sensitive), or GitHub Actions variables. Rotation is a Terraform operation that writes a new version to Secret Manager; the application picks up new values on its next startup, which is triggered by a Cloud Run revision deploy.

## Network posture

Each tenant project has a dedicated VPC. Cloud Run services use Direct VPC Egress to reach Cloud SQL and any internal resources. Ingress is through Cloud Load Balancing with a managed SSL certificate bound to the customer's custom domain.

For tenants with strict egress requirements, VPC Service Controls are configured to restrict the Cloud Run service to specific APIs and specific external destinations. For BYOC tenants, the customer typically enforces their own VPC Service Controls perimeter, and the vendor's deployment service account operates within that perimeter.

## Regional deployment

Each tenant is deployed to a single region (typically the region closest to the customer or dictated by their data residency requirements). Multi-region deployments within a tenant are not supported by the default topology and would require substantial additional complexity (Cloud SQL replicas, cross-region application deployment, DNS-based routing) that is not justified by the target market's latency expectations.

Disaster recovery is handled by Cloud SQL point-in-time recovery (backed up continuously, restorable to any point within the retention window) and GCS cross-region replication for bronze data (optional, enabled per tenant's disaster recovery requirements).
