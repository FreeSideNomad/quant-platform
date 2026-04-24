# Environment Flavours

The platform runs in five environment profiles, which differ in their deployment topology, data sources, and operational posture but share a single codebase and a single container image.

## Local

A full production simulation running on a developer laptop via docker-compose. Postgres with AGE, TimescaleDB, PGMQ, and pg_cron extensions. MinIO for blob storage. A mock OIDC provider substituting for customer identity providers. MLflow for model tracking. The application itself running under uvicorn with hot reload. The React UI served by Vite's dev server or by the application's static-serving middleware.

All code paths that exist in production execute locally. External data feeds are replaced by seed fixtures loaded from parquet files. Secrets come from a local `.env` file. Logs stream to stdout in JSON format, the same format used in production.

A new engineer runs `make dev` to bring up the stack, `make migrate` to apply schema changes, `make seed` to populate test tenants and users, and `make test` to run the full integration suite. The entire cycle completes without a network connection to GCP.

## Shared development sandbox

A shared GCP project containing a single instance of the platform used by the engineering team for exploratory testing, demos, and pre-merge integration. It mirrors production topology but uses smaller instance sizes, lower retention, and anonymised seed data. Access is via the team's Google Workspace; there is no per-tenant customer isolation.

The sandbox is not intended for customer data, customer demos, or performance testing. It exists to catch integration issues that the local stack cannot reproduce — real Cloud SQL behaviour, real Artifact Registry image pulls, real Workload Identity Federation tokens.

## Staging

A per-tenant replica of production, deployed in the vendor's GCP organisation, used for user acceptance testing before a customer promotes a release to their production silo. Identical configuration to the customer's production instance but pointed at the customer's UAT identity provider (or a dedicated staging realm within their corporate directory) and loaded with anonymised or synthetic data.

Staging exists for enterprise-tier customers. Standard-tier customers skip directly from the vendor's internal staging to their own production silo.

## Production silo

A dedicated instance of the platform per customer, deployed in the vendor's GCP organisation, isolated in its own GCP project. Contains a Cloud Run service (the application), a Cloud SQL Postgres instance with the full extension suite, a GCS bucket for blob storage, an MLflow tracking server, Secret Manager entries for the customer's identity provider configuration, and the customer's custom domain bound through Cloud Load Balancing.

The vendor operates the instance; the customer consumes it through their browser and through scheduled integrations pushing data into GCS. Lifecycle — provisioning, upgrades, monitoring, incident response — is managed by the vendor's control plane.

## Production BYOC

The same architecture as production silo, but deployed into a GCP project owned by the customer. The vendor retains a limited-scope service account with permissions to deploy new revisions, read telemetry, and run upgrade migrations. All data, including backups, lives within the customer's cloud perimeter.

BYOC is the deployment model of choice for customers with strict data residency obligations, regulatory oversight requiring on-premises equivalence, or internal policies prohibiting data egress to vendor-controlled environments. It is operationally heavier — the customer's change-management process applies to every release — but is often the only viable model for the largest customers.

## Comparison matrix

| Aspect | Local | Sandbox | Staging | Prod Silo | Prod BYOC |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Hosting | Laptop | Vendor GCP | Vendor GCP | Vendor GCP | Customer GCP |
| Isolation | Single-tenant | Shared | Per-customer | Per-customer | Per-customer |
| Identity | Mock OIDC | Vendor Workspace | Customer UAT | Customer prod | Customer prod |
| Data | Seed fixtures | Anonymised | UAT data | Production | Production |
| Cloud SQL size | Local container | db-f1-micro | db-custom-2-7680 | tier-appropriate | tier-appropriate |
| Min instances | 0 | 0 | 1 | 1 | 1 |
| Change cadence | Every commit | Every PR | Weekly | On customer approval | On customer approval |
| Observability | stdout | Shared dashboard | Per-tenant dashboard | Per-tenant dashboard | Per-tenant dashboard (often mirrored to customer) |
| Cost ownership | Vendor | Vendor | Vendor | Vendor | Customer |

## Environment selection at runtime

The application ships as a single container image. Environment differences are expressed entirely through:

- **Environment variables** resolving service endpoints (`DATABASE_URL`, `STORAGE_BACKEND`, `OIDC_PROVIDER_URL`, `MLFLOW_TRACKING_URI`)
- **Mounted secrets** from the local `.env` or from Secret Manager in the cloud
- **Feature flags** evaluated at startup for environment-specific behaviour (synthetic data injection, verbose logging, test endpoints)

No environment-specific code paths exist. A bug reproducible in production is reproducible locally by loading the same configuration.
