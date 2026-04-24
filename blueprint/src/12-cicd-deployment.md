# CI/CD and Deployment

## Pipeline overview

Every change flows through a single continuous-delivery pipeline hosted on GitHub Actions. The pipeline is driven entirely by repository events: pull-request creation, merge to `main`, tag creation, and manually-dispatched workflows for operational tasks.

The pipeline authenticates to Google Cloud using Workload Identity Federation. No long-lived service account JSON keys exist in GitHub secrets, in the repository, or anywhere else. The federation pool and provider are provisioned once, per GCP organisation, as part of the platform Terraform module.

## Runners — hosted and self-hosted

The pipeline uses two classes of runner with deliberately different trust postures.

**GitHub-hosted runners** (`runs-on: ubuntu-latest`) execute every job that processes untrusted code: PR checks, integration tests, image builds for PR preview, security scans. These jobs receive no secrets that could be exfiltrated from a fork PR. They build artefacts and push them to Artifact Registry using short-lived Workload Identity Federation tokens minted for the specific run.

**Self-hosted runners** execute every job that deploys an already-built image to a specific target environment. Self-hosted runners sit inside the target network and have the privileges required to operate on it — Docker socket access on a dev host, network access to a private Cloud SQL instance, VPN routes into a customer's on-premises environment. These runners never receive fork PR events; their workflows are restricted to the `main` branch and to `workflow_dispatch` triggers.

The dev/staging deployment target for this blueprint is a Docker Desktop host on an internal Windows server. A self-hosted runner installed on that host executes the dev deployment workflow; the runner has direct access to the local Docker daemon and pulls images from Artifact Registry using a service-account key scoped to `roles/artifactregistry.reader`. Production GCP deployments continue to use GitHub-hosted runners with Workload Identity Federation, because the target — Cloud Run in a customer's project — is reachable over the public internet with IAM-authenticated calls.

### Runner labelling

Self-hosted runners carry labels that workflows target explicitly:

| Labels | Target |
| :--- | :--- |
| `self-hosted, windows, docker-desktop, dev` | Dev Docker host on the internal Windows server |
| `self-hosted, linux, gke, staging` | Optional: GKE-resident runner for staging (used only when KEDA path is active) |
| `self-hosted, linux, byoc, tenant-{id}` | Per-tenant BYOC runner, provisioned in the customer's environment |

A workflow declares `runs-on: [self-hosted, windows, docker-desktop, dev]` to pin to the dev runner. Multiple runners can share the same labels for horizontal scaling; GitHub's scheduler picks an idle runner.

### Security posture for self-hosted runners

Self-hosted runners are a materially different trust boundary from hosted runners. The blueprint applies four controls:

1. **Branch restriction** — workflows using self-hosted runners trigger only on `push` to `main`, on tag, or on `workflow_dispatch`. Never on `pull_request` from untrusted sources.
2. **Repository-level only, not organisation-level** — the runner is registered to the specific repository, not to the org. This prevents any other repository in the org from accidentally scheduling a job on it.
3. **No secrets in repo** — secrets accessed by self-hosted runner jobs are fetched at runtime from the runner's own environment (Secret Manager via a workload identity on the runner host, or environment variables set by the runner service on startup). They do not flow through GitHub Actions secrets.
4. **Ephemeral execution** — the runner is configured for single-use ephemeral jobs where possible, so a job cannot leave state that affects a subsequent job.

### Installation on the dev Windows host

To install the self-hosted runner on the Windows Docker host:

1. On GitHub, navigate to **Repository Settings -> Actions -> Runners -> New self-hosted runner**. Select Windows, x64.
2. On the Windows host, open PowerShell as Administrator in the target directory (for example `C:\actions-runner`).
3. Follow the commands GitHub provides — `Invoke-WebRequest` to download the runner, `./config.cmd` to register it, and `./svc.sh install` / `./svc.sh start` to run it as a Windows service. Apply the labels `self-hosted,windows,docker-desktop,dev` during registration.
4. Grant the runner service account access to the Docker Desktop user's named pipe. The simplest path is to install the runner service as the same Windows account that runs Docker Desktop; alternatively, add the runner's service account to the `docker-users` local group.
5. Verify by triggering a workflow with `runs-on: [self-hosted, windows, docker-desktop, dev]`; the job should start on the Windows host within seconds.

Maintenance of the runner is an operational responsibility. The runner auto-updates its agent binary; the Windows host, Docker Desktop version, and installed tooling (Python, Node) are the operator's responsibility.

![Blue/green deployment flow](diagrams/rendered/08-bluegreen-flow.pdf){width=95%}

## Pipeline stages in detail

The pipeline is a graph of stages, each running in an isolated GitHub Actions job. Stages that are independent run in parallel; stages with dependencies run sequentially. A representative concrete pipeline:

### Stage 1: Source checkout and toolchain setup

Every job begins by checking out the repository at the triggering commit and preparing the toolchain.

- **Python**: `setup-uv` action installs `uv` at a pinned version; `uv sync --frozen` reads `uv.lock` and produces an identical virtual environment to the one engineers use locally. Caching uses the hash of `uv.lock` as the cache key, so a lockfile change invalidates the cache but nothing else does.
- **Node**: `setup-node` action at a pinned version; `npm ci` from `package-lock.json`. Cache keyed on the lockfile hash.
- **Docker Buildx**: enabled for multi-platform image builds (`linux/amd64` for production, `linux/arm64` for local parity on Apple Silicon).

This stage completes in seconds when caches hit.

### Stage 2: Static checks (parallel fan-out)

Three jobs run in parallel:

- **Lint**: `ruff check` across the Python codebase; `eslint` and `prettier --check` across the frontend; `terraform fmt -check` across infrastructure.
- **Type-check**: `pyright --project pyproject.toml` for Python; `tsc --noEmit` for TypeScript.
- **Security scan**: dependency vulnerability scan via `pip-audit` against the uv-resolved environment (to be replaced by a `uv audit` first-party command once Astral ships it); GitHub Dependency Review on the lockfile; secret-pattern scan via `trufflehog` or equivalent.

Any failure here terminates the pipeline. These checks complete in under a minute.

### Stage 3: Unit tests

- **Python unit**: `pytest -m unit` — tests in the domain and application-core modules with no external dependencies. Completes in tens of seconds.
- **Frontend unit**: `vitest run` — React component and utility tests. Completes in tens of seconds.

### Stage 4: Integration tests

A single job that:

1. Brings up the docker-compose stack (`make dev`, or a CI-specific compose file).
2. Runs Alembic migrations (`make migrate`).
3. Seeds the database with the canonical test fixtures (`make seed`).
4. Runs the full integration suite (`pytest -m integration`) against the live stack.
5. Tears down the stack on completion.

The integration stage takes the longest of any single job — typically three to six minutes — but it validates the behaviour that matters most: the application working end-to-end against real Postgres, real PGMQ, real MinIO, real MLflow, real mock-OIDC.

### Stage 5: Frontend build and E2E tests

- `npm run build` produces the production React bundle.
- The bundle is served alongside the application (either mounted into the FastAPI container or served by Vite preview, depending on the test variant).
- `playwright test` drives the full stack through the UI, exercising the login-to-inference user journey.

Playwright runs headless in CI; engineers can reproduce the same tests locally with `--headed` for debugging.

### Stage 6: Container image build

Once all tests pass, a single job builds the application container:

1. Multi-stage Dockerfile: a `builder` stage installs dependencies with `uv sync --no-dev --frozen`, compiles any native code, and builds the frontend bundle. A `runtime` stage copies only the built artefacts onto a minimal base image (Chainguard Python or Distroless).
2. Buildx produces `linux/amd64` (and optionally `linux/arm64`) images.
3. The image is tagged with three labels: the semantic version (`v1.4.2`), the version with commit SHA (`v1.4.2-abc1234`), and the floating tag `main-latest`. Pull-request builds use `pr-{number}` tags instead.
4. The image is pushed to Artifact Registry at `{region}-docker.pkg.dev/{platform-project}/apps/quant-platform`.
5. Artifact Registry's built-in vulnerability scanner runs asynchronously after the push.

### Stage 7: Staging deployment (main branch only)

On merge to `main`, the pipeline deploys the new image to the staging tenant. Because the application runs as multiple Cloud Run services stamped from the same image — one per role (`api`, `worker-proj-ui`, `worker-proj-graph`, `worker-pipeline-bronze`, `worker-training`, and so on) — the deployment fans out across every service in the tenant's deployment set.

1. A migration job (`gcloud run jobs execute`) runs Alembic against the staging Cloud SQL instance, applying forward-compatible schema changes.
2. For **each** Cloud Run service in the tenant's deployment set, a new revision is created with `--no-traffic` using the new image tag. The same image URI is used for every service; only the `ROLE` env var differs.
3. Smoke-test jobs run against the new revisions' direct URLs. `api` smoke tests cover authentication, a representative command, a representative query, and a training submission. Worker smoke tests enqueue a test message and assert it is processed.
4. If all smoke tests pass, traffic is shifted in steps across all services (10% -> 50% -> 100%) with a two-minute pause between steps for metric observation. Each step is a `gcloud run services update-traffic` invocation per service; the pipeline parallelises across services.
5. Old revisions are retained for twenty-four hours to support rapid rollback; after that, they are automatically pruned.

The failure of any single service's smoke test or traffic shift pauses the fan-out and reverts traffic on services that have already been shifted. Deployment is transactional at the tenant level, not at the individual-service level — either every service advances or none does.

### Stage 8: Production rollout (control-plane-driven)

Production tenant deployments are not triggered directly by the GitHub Actions pipeline. The successful staging deployment emits an event that the control plane receives, recording the image as "available for production." The control plane then orchestrates the wave-based rollout described below, scheduling per-tenant deployments within their maintenance windows.

## Workload Identity Federation concretely

The pipeline never holds a GCP credential. Instead, GitHub's OIDC token is exchanged for a short-lived GCP access token at the start of each job that needs GCP access. The mechanism:

1. Once per GCP organisation, a Workload Identity Pool and a GitHub OIDC Provider are provisioned by Terraform. The provider binds the pool to the GitHub organisation and, optionally, to a specific repository or branch.
2. A service account per environment (`ci-staging@...`, `ci-production@...`) is granted `roles/iam.workloadIdentityUser` on the pool, with an attribute condition matching the expected repository and branch.
3. The service account has the minimum IAM roles for its intended operations: Artifact Registry writer for image-push jobs, Cloud Run deployer for deployment jobs, and so on.
4. In the GitHub Actions workflow, the `google-github-actions/auth` action performs the token exchange and sets up the gcloud CLI and the Google client libraries to use the exchanged credential.

This pattern is the current best practice for GitHub Actions authenticating to Google Cloud and is well documented in the `google-github-actions` repository.

## Workflow file structure

GitHub Actions workflows live in `.github/workflows/` and are organised by trigger:

| Workflow | Trigger | Purpose |
| :--- | :--- | :--- |
| `pr.yml` | `pull_request` | Full test suite, container build with PR tag, optional preview deploy |
| `main.yml` | `push` to `main` | Re-runs tests, publishes image with `main-latest`, deploys to staging |
| `release.yml` | Semantic version tag (e.g. `v1.4.2`) | Publishes release image, notifies control plane |
| `infra.yml` | Changes under `terraform/` | Terraform plan on PR, apply on merge |
| `tenant-deploy.yml` | `workflow_dispatch` from control plane | Deploys a specific image tag to a specific tenant |
| `nightly.yml` | Scheduled | Drift detection, dependency updates, long-running integration tests |

Each workflow reuses composite actions in `.github/actions/` — `setup-python`, `setup-frontend`, `gcp-auth`, `build-and-push` — so repetition is minimised and changes to the toolchain touch a single location.

## Pipeline performance expectations

With the toolchain described above, the end-to-end time for a pull-request pipeline is expected to fall in the five-to-eight-minute range on standard GitHub-hosted runners, with the majority of that time spent in the integration and E2E stages. Unit tests and static checks complete in under two minutes combined. Container build is typically one to two minutes.

The main-branch pipeline extends this by approximately five to ten minutes for the staging deploy plus smoke test plus gradual traffic shift. Production tenant rollouts, orchestrated by the control plane, proceed on per-tenant maintenance windows and are measured in hours per wave rather than minutes.

## Failure modes and their handling

- **Test flake** — flaky tests are quarantined (moved to an ignored marker) on first occurrence and tracked in an issue. The quarantine is a forcing function: a flaky test is a broken test and must be fixed or deleted.
- **Transient registry failures** — image push retries are built into the pipeline with exponential backoff.
- **Deploy failure mid-rollout** — automatic traffic reversion to the previous revision; the pipeline is marked failed; the control plane is notified if the failure was on a tenant.
- **Migration failure** — migrations run as a separate job before deployment; a migration failure blocks deployment without leaving the database in an inconsistent state. Forward-compatible migration design means the prior revision continues to work.
- **Smoke test failure** — the green revision is drained; the traffic shift does not proceed; an alert is raised.
- **Post-deployment metric regression** — if the control plane observes elevated error rates after a rollout, it halts the wave and can automatically roll back by re-running the deployment with the prior image tag.

## Pull request workflow

On every pull request, the `pr` workflow runs the following in parallel where possible:

1. **Lint and format** — ruff for Python, eslint and prettier for TypeScript
2. **Type check** — pyright for Python, tsc for TypeScript
3. **Unit tests** — the pytest unit suite
4. **Integration tests** — bring up the docker-compose stack, run the integration pytest suite against it
5. **Frontend build** — `npm run build` producing the static React artefacts
6. **End-to-end tests** — Playwright against the running local stack with the built frontend
7. **Container build** — build the application container image, tag with the PR number and commit SHA, push to Artifact Registry
8. **Security scan** — Artifact Registry vulnerability scan on the pushed image; fail the PR if critical CVEs are detected
9. **Terraform plan** — for any changes under `terraform/`, run `terraform plan` and post the plan as a PR comment

Optional per-PR preview deployments are available: a manually-triggered workflow deploys the PR image to a short-lived Cloud Run revision in the sandbox project and posts the preview URL back to the PR. These are used for UI review and for cross-team demos, not as a substitute for local testing.

## Main branch workflow

On merge to `main`, the `main` workflow:

1. Re-runs the full PR workflow (unit, integration, e2e, container build, scan)
2. Tags the container image as `{semver}-{sha}` and as `main-latest` in Artifact Registry
3. Deploys the new image to the staging tenant instance with zero traffic (a green revision alongside the existing blue)
4. Runs an automated smoke test suite against the green revision's direct URL
5. Shifts traffic to the green revision in increments (10%, 50%, 100%) with health checks between each step
6. If the smoke tests or health checks fail, automatically reverts traffic to the blue revision and marks the deployment failed
7. On success, queues the image for rollout to production tenants per their maintenance windows

Staging deployments are automatic and continuous. Production deployments are coordinated by the control plane and respect per-tenant upgrade preferences.

## Publishing to Artifact Registry

The application's container image is the single deployment artefact. It is built once, on merge to `main`, and promoted unchanged through the environment progression (staging -> canary tenants -> general fleet).

Publishing workflow:

1. The GitHub Actions runner authenticates to GCP via Workload Identity Federation, assuming a service account with `roles/artifactregistry.writer` on the platform project's registry.
2. The image is built with Docker Buildx, targeting both `linux/amd64` and optionally `linux/arm64` for local development parity on Apple Silicon laptops.
3. The image is tagged with the semantic version (`v1.4.2`), the git commit SHA (`v1.4.2-abc1234`), and the floating tag `main-latest`.
4. The image is pushed to `{region}-docker.pkg.dev/{platform-project}/apps/quant-platform:{tag}`.
5. A post-push job triggers Artifact Registry's vulnerability scanner. Critical findings are posted back to the repository as an issue.

Artifact Registry has lifecycle rules that retain the last fifty images tagged with semantic versions indefinitely and delete untagged or PR-tagged images after fourteen days. This keeps registry costs bounded while preserving the ability to roll back to any recent release.

## Blue/green deployment on Cloud Run

Cloud Run's native revision model is the blue/green primitive. Each deploy creates a new revision; traffic is distributed across revisions via an explicit traffic configuration. Rollback is a configuration change, not a rebuild.

A tenant deployment is a **set** of Cloud Run services, one per role, all stamped from the same image. Blue/green applies per service, and the control plane orchestrates the fan-out so that either all services advance to the new image or all revert. The deployment dance, orchestrated by the control plane for each tenant, proceeds as follows — where each numbered step is executed across every service in the deployment set:

1. **Deploy a new revision with zero traffic:**
   ```
   gcloud run deploy {service} \
     --image {registry}/{app}:{version} \
     --region {region} \
     --no-traffic \
     --revision-suffix {version}
   ```
2. **Run migrations** as a separate Cloud Run Job against the tenant's database. Migrations are always forward-compatible — the new revision must work with both the old schema (pre-migration) and the new schema (post-migration). This is enforced by a migration-check test in the PR workflow.
3. **Smoke test the green revision** directly at its unique URL (`{revision}---{service}-{hash}-{region}.a.run.app`). Smoke tests exercise authentication, a representative command path, a representative query path, and the training submission endpoint.
4. **Gradual traffic shift:**
   ```
   # 10% to green
   gcloud run services update-traffic {service} \
     --to-revisions={green}=10,{blue}=90
   # wait, check metrics
   # 50%
   gcloud run services update-traffic {service} \
     --to-revisions={green}=50,{blue}=50
   # wait, check metrics
   # 100%
   gcloud run services update-traffic {service} \
     --to-revisions={green}=100
   ```
5. **Retain the blue revision** for a configured window (typically twenty-four hours) to support rapid rollback.
6. **Emit deployment events** to the control plane's event log: tenant, version, timestamp, outcome.

Rollback at any step is:

```
gcloud run services update-traffic {service} --to-revisions={blue}=100
```

A single command, no rebuild, and traffic shifts in seconds.

## Forward-compatible migrations

Blue/green deployment is only viable when the database schema is forward-compatible — new revisions must not require schema changes that break old revisions. The expand-migrate-contract pattern enforces this:

1. **Expand** — add new columns, tables, or indexes in an additive migration. Both old and new code work.
2. **Deploy new code** that begins using the new schema while continuing to write old fields for the duration of the overlap window.
3. **Backfill** — a separate job populates the new columns from existing data.
4. **Contract** — a later release removes the old columns. This requires all running revisions to be on the new code.

This pattern adds a release cycle to every schema change but eliminates a class of downtime incidents. It is enforced in CI by a check that runs the migration, starts the old revision against the new schema, and exercises a representative test suite. If the old revision breaks, the migration is rejected.

## Fleet upgrade orchestration

Production tenants are on different versions at any given moment — this is a natural consequence of silo tenancy. The control plane tracks per-tenant versions and orchestrates rollouts in waves:

1. **Canary wave** — one or two internal test tenants. Deploy, observe for twenty-four hours.
2. **Early-adopter wave** — customers who have opted into faster releases. Deploy, observe for forty-eight hours.
3. **General wave** — the majority of tenants. Deploy during their maintenance windows over a one-to-two-week period.
4. **Conservative wave** — customers on the slowest track (typically enterprise contracts with strict change control). Deploy after a month of fleet-wide stability on the new version.

Each wave has a defined success criterion (error rate, latency, customer-reported issues). Failure in one wave pauses the rollout and triggers investigation. The control plane enforces these pauses automatically; they are not dependent on human diligence.

## Blue/green across the full stack

The Cloud Run revision-based blue/green covers the application. The full deployment surface also includes MLflow, Cloud SQL (schema migrations), and GCS buckets (immutable data).

- **MLflow** uses the same Cloud Run revision model, with its own blue/green flow. Because MLflow is stateless (state lives in Postgres and GCS), revision rollback is instant.
- **Cloud SQL** migrations are forward-compatible, as described above. Rollback of a migration is avoided; instead, the next release rolls forward to fix any issue.
- **GCS buckets** are immutable — deployment doesn't change bucket contents, only application reads and writes.

## CI/CD for Terraform

Infrastructure changes flow through a parallel pipeline. Terraform code lives in the same repository as the application. On PR, `terraform plan` runs for every changed workspace and posts the plan as a comment. On merge to `main`, `terraform apply` runs automatically for the platform workspace and for non-production tenant workspaces; production tenant applies require a manual approval step in GitHub Actions.

Terraform state is remote (GCS bucket in the platform project, per-workspace). State locking prevents concurrent applies. Drift detection runs nightly and alerts on any unmanaged changes.

### Is Terraform overkill?

The question deserves a direct answer rather than reflexive defence of the choice. Terraform adds a configuration language to learn, a state-management concept to maintain, a plan-and-apply discipline to follow, and a class of state-corruption failures to recover from. For a single tenant, a shell script calling `gcloud` commands is legitimately simpler and does the job.

The trade-off tips in favour of Terraform at the point where infrastructure becomes repeatable rather than bespoke. Concretely:

- **One tenant forever, no BYOC, no planned fleet growth.** A `gcloud`-based shell script or a set of Makefile targets is sufficient and arguably preferable. Don't add Terraform for its own sake.
- **Two or more tenants, or any realistic expectation of more.** Terraform's value appears immediately. The module-per-tenant pattern, variable-driven customisation, and remote state make every new tenant a variable change rather than a script rewrite. Drift detection catches manual console edits before they become silent incidents.
- **BYOC at any scale.** Terraform is essentially required. BYOC deployments demand strict, reviewable, auditable definitions of exactly what is being provisioned in the customer's project; customers will ask to see the module, review it, and sometimes run their own plan against it. A shell script is not a defensible artefact in a customer security review.
- **Regulated tenants, SOC 2 ambitions, or any compliance framework.** Terraform's reviewability and state auditability are directly required by every modern compliance framework that examines infrastructure controls. Auditors accept Terraform as evidence; they do not accept "we ran some gcloud commands."

The specific CI-integration patterns with GitHub Actions are three:

- **Direct `terraform` CLI in the runner** — the simplest pattern. A workflow checks out the repo, authenticates to GCP via Workload Identity Federation, runs `terraform init` / `plan` / `apply`, and posts results as PR comments. State lives in a GCS bucket; locking is handled by Terraform's native GCS backend.
- **Terraform Cloud / Terraform Enterprise** — HashiCorp's managed runner service, invoked from GitHub Actions via API calls. Adds cost and an external dependency; provides a polished UI, run history, and policy-as-code. Worth considering only for teams whose operations involve stakeholders outside engineering who benefit from the UI.
- **Atlantis** — a self-hosted runner for Terraform that integrates with GitHub PR comments. Useful for larger teams with many concurrent infrastructure PRs; overkill for a single-team product.

For the blueprint's default, the direct-CLI pattern is the right choice. It keeps everything in GitHub Actions, avoids a second SaaS dependency, and is trivially substitutable for Terraform Cloud later if the team demands a UI.

### Alternatives to Terraform, briefly

**Pulumi** — defines infrastructure in Python (or TypeScript, Go). Attractive to a Python-first team because it shares the language; potentially unified with application code. Downsides: smaller ecosystem, smaller pool of engineers familiar with it, less-mature support for some GCP services. A reasonable choice for a Python-only team; not the default recommendation because the declarative separation of infrastructure from application code is a feature, not a bug.

**Config Connector / KCC** — GCP's Kubernetes-style declarative resource API. Excellent if the platform already runs on GKE and wants to manage everything through Kubernetes manifests. Misaligned with a Cloud Run-centric architecture; adds a Kubernetes dependency that does not otherwise exist.

**gcloud scripts** — a defensible choice only for a single-tenant scenario with no compliance obligations and no planned growth. Revisit immediately when the context changes.

## Release testing: platform tests versus customer-specific tests

A new release must be safe for every tenant it will be deployed to. "Safe" has two distinct meanings, and the testing strategy must address both.

**Platform safety** — the new release does not introduce bugs in the platform's own behaviour. Every command path still works, every query path still works, schemas migrate correctly, auth still functions, the UI still renders. This property is tested once per release in CI and must pass before any tenant sees the new image.

**Tenant safety** — the new release does not break anything specific to a particular tenant's configuration, data sources, models, or workflows. A release that is fine on tenant A may break on tenant B because tenant B has a data source that uses a feature the release changed, or a model that depends on a library version the release bumped, or an authorisation configuration the release refactors. This property must be tested per tenant, against tenant-specific state, and is irreducible — a platform-level test suite cannot cover it because the test suite does not know what each tenant cares about.

### Platform test suite

The platform test suite runs in CI on every pull request and every merge to `main`. It is entirely tenant-agnostic; it uses seed data that represents a generic customer but does not represent any real customer.

| Layer | Coverage |
| :--- | :--- |
| Unit | Domain logic, aggregates, pure functions |
| Contract | OpenAPI schema, event schema, migration compatibility |
| Integration | Full REST API against docker-compose stack, real Postgres, real PGMQ, real MinIO, real MLflow |
| End-to-end | Playwright-driven UI journeys |
| Performance | Representative load tests against synthetic data |
| Security | Static analysis, dependency scanning, container image scanning |

The platform suite is the gate between "code merged" and "image promoted to Artifact Registry." An image that has not passed the full platform suite cannot be deployed to any tenant.

### Tenant smoke tests

Each tenant has a smoke-test suite exercising the tenant's specific configuration at the API level. Smoke tests are small — seconds to a few minutes — and cover:

- Authentication against the tenant's configured identity provider (using a dedicated service-account-style test identity)
- A representative command invocation (e.g. submit a training run for a production model)
- A representative query invocation (e.g. fetch the model list, fetch the last inference result)
- File-based ingestion path (drop a small test file, confirm it reaches gold)
- File-based export path (trigger an export, confirm it appears in the expected location)

Smoke tests run automatically after every tenant deployment as part of the blue-green rollout — the green revision is smoke-tested against its direct URL before any production traffic is shifted. A failing smoke test reverts the traffic shift and raises an alert.

Smoke tests are maintained in the platform repository, parameterised by tenant configuration. Adding a smoke test is a platform engineering activity; adjusting it for a specific tenant's quirks is a configuration change.

### Customer-specific regression tests

Above smoke tests, customers (particularly enterprise-tier customers) own a test suite that exercises their specific workflows, data sources, and models in ways the platform suite cannot anticipate. These tests are:

- **Provided by the customer** in a repository the platform can execute against their staging environment
- **Executed by the platform** on every upgrade to their staging instance, before promotion to their production silo
- **Blocking** — a failure pauses the customer's upgrade; the customer must approve proceeding or ask for a fix

This layer is the explicit contract between the platform and the customer: the platform promises not to break what the customer has tested. The customer promises to maintain the test suite as their usage evolves. Neither party tests for the other.

Customers who do not maintain a test suite are on their own smoke-test coverage and implicitly accept the risk of tenant-specific regressions. Most enterprise customers build such suites within their first quarter on the platform; the platform supplies templates and runs the tests in their staging environment.

### Upgrade-wave testing

The wave-based rollout (canary -> early adopter -> general -> conservative) is itself a testing layer. Each wave produces observable signals:

- Error rates and latency on the rolled-out tenants
- Customer-reported issues
- Smoke-test failures
- Customer-owned regression suite failures

A wave that produces any negative signal halts the rollout. The next wave does not begin until the signal is resolved. This structure means that a regression in a rare configuration — one that is missed by both the platform suite and the customer's own suite — is caught on a small population before reaching the majority of the fleet.

### What not to test

Platform CI should not execute customer-specific tests. Customer staging environments should not execute platform CI suites. The two layers are deliberately separate: the platform tests that its invariants hold; the customer tests that its workflows work. Mixing them produces a test suite that is slow, fragile, and expensive to maintain, without improving the safety property either layer provides on its own.

The platform's responsibility ends at the contract it publishes (REST API, file contracts, event schemas, UI surface). The customer's responsibility begins at how they use that contract. Test each on its own side of the line.
