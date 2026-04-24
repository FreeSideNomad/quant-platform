# Security and Compliance

## Threat model

The primary threat classes the platform defends against:

1. **Cross-tenant data access** — a user or compromised credential for tenant A gaining access to tenant B's data. Mitigated by the silo topology: tenants share no database, no storage, no compute, and no IAM principal. Cross-tenant access requires crossing a GCP project boundary, which is the strongest isolation primitive GCP offers.

2. **Model IP exfiltration** — an attacker extracting trained models or training data. Mitigated by tenant-scoped Secret Manager and GCS bucket IAM, per-tenant service account binding to Cloud Run and MLflow, and BYOC for customers whose threat model excludes vendor-side access.

3. **Identity impersonation** — an attacker assuming another user's identity within a tenant. Mitigated by delegating authentication to the customer's directory (with its MFA, conditional access, and anomaly detection), short-lived session JWTs, and revocation via the `jti` registry.

4. **Supply-chain compromise** — malicious code introduced through a dependency or build artefact. Mitigated by pinned dependency versions (`uv.lock`, `package-lock.json`), Artifact Registry vulnerability scanning on every push, and Software Bill of Materials (SBOM) generation in CI.

5. **Misconfigured IAM** — overly permissive IAM bindings exposing resources. Mitigated by Terraform-driven IAM (no console edits), least-privilege role assignments validated by Policy Analyzer, and a nightly drift check.

6. **Data exfiltration through the application** — a legitimate user exceeding their authorised scope. Mitigated by role-based authorisation at every handler, domain-level permission checks, and the inference log for post-hoc auditability.

## Tenant isolation

The silo tenancy model is the primary isolation boundary. Each tenant has:

- A dedicated GCP project with its own IAM policy, billing account, and quota.
- A dedicated VPC, restricting network paths to the application's own services.
- A dedicated Cloud SQL instance, with its own connection endpoint and credentials.
- A dedicated GCS bucket, with bucket-level IAM excluding cross-tenant access.
- A dedicated Secret Manager namespace, with secrets scoped to the tenant's service account.
- A dedicated Artifact Registry pull permission (images are shared; pull access is per-project).

There is no code path in the application that could traverse tenants; the application runs in a single tenant's context and does not have IAM permissions to reach any other tenant.

## Encryption

All data is encrypted at rest by default using Google-managed encryption keys. Customers with heightened requirements opt into Customer-Managed Encryption Keys (CMEK) backed by Cloud KMS. Key rotation is enforced on a policy schedule; the application reads the current key version from the resource API on each operation.

All data in transit is encrypted via TLS 1.3 at every hop: browser-to-load-balancer, load-balancer-to-Cloud Run, Cloud Run-to-Cloud SQL (IAM auth tokens), Cloud Run-to-GCS (HTTPS), Cloud Run-to-MLflow (HTTPS). Internal VPC-only traffic is encrypted by Google's transparent network encryption.

For BYOC customers, encryption keys are held by the customer in their own KMS. The application is given wrap/unwrap permission but not read permission on the key material itself.

## Secret handling

Secrets never appear in:
- Container images (scanned on push to catch accidental inclusion)
- Git history (pre-commit hook scans for credential patterns)
- Terraform state files (Secret Manager values are marked `sensitive` and referenced, not embedded)
- Application logs (a log-sanitisation middleware redacts values matching secret patterns)
- GitHub Actions environment variables (WIF replaces all static credentials)

The application's secret-loading layer reads from Secret Manager at startup, caches values in memory for the lifetime of the container, and never writes them to disk or logs. Rotation is achieved by deploying a new revision; the old revision drains with the old secret, and the new revision starts with the new secret.

## Audit requirements

Regulated customers in the hedge-fund segment typically have audit requirements driven by SEC, CFTC, FINRA, or equivalent non-US regulators. The platform supports these through:

- **Immutable event store** — the append-only `events` table is the source of truth for every domain change; it cannot be modified, only appended to. Historical events can be replayed to reconstruct state at any point in time.

- **Bi-temporal data** — corrections to historical data are recorded alongside the original values, with explicit validity ranges. Training data extractions reproduce historical states faithfully.

- **Inference log** — every model inference is recorded with its inputs, outputs, model version, and requesting user. Correlating a trading or risk decision to its informing inference is a single query.

- **Cryptographically-chained audit trail** — the application-level audit log uses per-row hash chaining to detect tampering. A tamper check is part of the daily backup verification.

- **WORM retention** — audit logs and inference logs are exported to GCS buckets with Object Lifecycle Lock, making them irrevocable for the retention period (typically seven years).

- **Export on demand** — regulators and customer auditors can request an export; the platform provides a self-service export endpoint that produces a signed, timestamped archive of audit data for a date range.

## Data residency

Each tenant is deployed to a specific region, dictated by the customer's residency requirements. The Terraform module accepts the region as an input and configures Cloud Run, Cloud SQL, and GCS accordingly. Cross-region data movement is disabled by default; enabling it (e.g. for disaster-recovery replication) requires an explicit configuration change and is documented in the tenant's configuration file.

Common residency targets:
- **US**: `us-central1` or `us-east4`
- **EU**: `europe-west1` (Belgium) or `europe-west3` (Frankfurt)
- **UK**: `europe-west2` (London)
- **Asia**: `asia-northeast1` (Tokyo) or `asia-southeast1` (Singapore)

For customers with split residency requirements (e.g. a European customer whose London office handles UK-domiciled data and whose Frankfurt office handles EU-domiciled data), the solution is multiple tenant instances, one per jurisdiction, not a single multi-region instance.

## BYOC-specific considerations

BYOC deployments introduce an additional layer of access control: the vendor's deployment service account has access only to the specific resources required for lifecycle operations. Typical BYOC IAM grants are:

- `roles/run.developer` on the tenant's Cloud Run services — for deploying new revisions
- `roles/cloudsql.client` on the Cloud SQL instance — for running migrations
- `roles/artifactregistry.reader` on the vendor's Artifact Registry — for pulling images
- `roles/monitoring.viewer` on the tenant's project — for observability access
- `roles/logging.viewer` on the tenant's project — for troubleshooting

The vendor's service account does not have `roles/editor` or `roles/owner` on the customer project. It cannot create new resources, delete existing resources, or modify IAM policies. Structural changes (adding a new service, changing a network boundary) require customer-side action.

The customer provides VPC Service Controls boundaries, organisation policies, and audit log retention on their own terms. The vendor's deployment service account operates within those constraints.

## Vulnerability management

Every dependency is tracked and scanned:

- **Python dependencies** — `uv.lock` pins exact versions; GitHub's Dependabot proposes upgrades for security advisories.
- **JavaScript dependencies** — `package-lock.json` pinning and the same Dependabot coverage.
- **Container base image** — a Distroless or Chainguard Python image, minimising attack surface and patched upstream.
- **Container image scanning** — Artifact Registry's built-in scanner flags vulnerabilities on every push; critical findings block deployment.
- **Terraform modules** — pinned to specific registry versions; upgrades reviewed as regular PRs.

A security review of the SBOM runs on a monthly cadence. The output feeds the engineering backlog.

## Incident disclosure

Security incidents follow an accelerated version of the normal incident response process. The runbook includes a mandatory customer notification step for any incident classified as data-impacting or authentication-bypassing, with a time-to-notification commitment (typically twenty-four to seventy-two hours) documented in the master services agreement.

Customers in regulated industries often require contractual disclosure obligations; these are negotiated per contract and implemented in the platform's incident playbook rather than in code.
