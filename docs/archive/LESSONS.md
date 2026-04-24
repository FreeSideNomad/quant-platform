# Lessons from the MVP-A attempt (parked 2026-04-22)

> Honest retrospective on the rushed MVP-A build. Read this BEFORE brainstorming the next iteration.
>
> The code is preserved on GitHub (`archive/mvp-a-rushed-2026-04-22` branch + `archive-mvp-a-2026-04-22` tag) and locally at `../deployment/quant-platform-archive-2026-04/`. Reference it when useful — don't repeat its mistakes.

---

## What we built

A 38-commit run that landed in ~24 hours:
- 23 implementation tasks (TDD-driven, 110 → 114 tests green)
- "Honest hardening" pass on top (F0–F5 fixes + H1–H3 doc honesty)
- Working: BFF + IdP federation, audit log with hash-chain, walk-forward gate, PBO/DSR/CPCV honesty checks, MLflow registry with Aliases (eventually), Dagster medallion (bronze/silver/gold) + walk-forward assets, BFF reverse-proxy of Dagster (HTTP + WebSocket), Bearer-JWT GraphQL passthrough on the API
- Demo workload: synthetic OHLCV → Polars rolling features → LightGBM. **Not** Qlib, **not** CSI 300, **not** Alpha158.

Every test passed. The architecture was wrong anyway.

---

## The core mistake

**"Add Dagster everywhere"** was the worst call of MVP-A. It was made mid-build, after the original design (PGMQ + APScheduler + worker) was already working. The cost compounded across every subsequent task: code-locations watcher, software-defined assets, separate webserver + daemon processes, GraphQL API needing reverse-proxying, and — the worst by-product — a per-strategy code-generation pattern that wrote Python files to disk from JSON specs.

For demo-scale (one user, one workload, local docker-compose), Dagster bought us **nothing demoable** that PGMQ + a worker couldn't produce, and it tripled the failure surface.

The "honest hardening" pass ripped the codegen back out (F0) but left Dagster as the orchestrator because the cost was already paid. A fresh-start MVP should not import Dagster at all until a customer pipeline justifies it.

---

## Specific failures (by topic)

### Architectural

1. **Per-strategy Dagster codegen (RCE-shaped).** `RegisterStrategy` wrote generated Python files into `app/dagster_defs/strategies/<slug>.py`, picked up by Dagster's code-locations watcher. `_slugify()` was the only barrier between a JSON spec submission and code on disk. Removed in F0, but the underlying lesson is: **never let user input drive code-on-disk patterns**, no matter how clever the slugifier.

2. **Bronze cache hardcoded to `/tmp/bronze_cache.parquet`.** Concurrent Dagster runs corrupted each other; container restart lost state. Fixed in F1 with per-run UUIDs in asset metadata, but the deeper issue is that the cache existed at all — it was a hack to bridge two assets that should have been one materialization.

3. **MLflow Aliases vs Stages mismatch.** SDK design spec committed to MLflow Aliases. Promotion gate code wrote `model_versions.stage` directly and never called the alias API. The code lied about the spec for ~20 commits before the gap was noticed. Lesson: **specs and code drift fast under speed pressure**; CI should enforce alignment, not author memory.

4. **No de-registration anywhere.** Strategies, generated files, MLflow runs, audit-log entries — all accumulated. Garbage collection / lifecycle was treated as Phase 2.

### Security

5. **No CSP, X-Frame-Options, X-Content-Type-Options on the BFF.** Browser-facing service shipped with default headers. Fixed in F3, but it should have been Day 1.

6. **`StrategySpec.family` was free-text.** Validators were `family: str`. Even after F0 removed the codegen path, F5 had to add regex `^[a-zA-Z][a-zA-Z0-9_-]*$` and 64-char limits. Defense in depth means **never trust free-text from a JSON spec**, even when "no current path uses it dangerously."

7. **`IDP_SIGNING_KEY_B64` hardcoded as env var.** Documented in deferred work, never wired to a secret manager. OK for dev; would not survive a security review.

### Honesty

8. **"Qlib reference workload" overclaim.** Marketing language ("Qlib port", "Qlib reference workload") implied port-fidelity that didn't exist. Actual workload: synthetic OHLCV. Softened in H1.

9. **Multi-tenancy claim was deployment-layer only.** Blueprint said "silo tenancy." True at the GCP-project level (one project per tenant). False at the query layer (no `tenant_id`, no scoped SELECTs). If two tenants ever shared a database — which the architecture forbids but doesn't enforce — they'd see each other's data. Documented in H2.

10. **MVP scope inflated mid-build.** Started as "demoable MVP," became "MVP + Dagster everywhere + walk-forward gates + medallion architecture + reverse-proxied orchestration UI." The 5,840-line plan was the symptom; the cause was no checkpoint with the user between brainstorming and execution.

### Process

11. **No user feedback loop during execution.** "Use max parallel agents until CPU melts" was taken at face value. 23 tasks, 38 commits, no checkpoint. By the time the architectural review surfaced the problems, the cost was sunk.

12. **TDD was rigorous but at the wrong level.** Every task had failing-test-first discipline. None of the tests asked "is this the right shape?" Test-driven development is necessary, not sufficient.

13. **Schema drift between plan and reality.** `inference_log` had `instrument, as_of_date, feature_hash, prediction` (existing) — the plan said `request_payload, response_payload`. Multiple tasks had to be reworked when the actual schema came into view. Plans must verify-then-write.

---

## Pre-Dagster thinking (preserved)

Before "add Dagster everywhere," the architecture was simpler and aligned with the golden rule of full local prod simulation (see `memory/feedback_architecture_monolith.md`):

- **Messaging:** PGMQ (Postgres extension). All queues live in the same Postgres instance as the audit log, strategies, and inference log. One backup, one connection pool, one transactional boundary.
- **Scheduling:** APScheduler embedded in the API process, or a tiny scheduler role in the multi-role image. Cron-like, in-process, no external daemon.
- **Workers:** Long-running Python processes that `LISTEN` on a PGMQ queue, pull a job, run it, write results back to Postgres / MLflow / GCS. No DAG framework — just `while True: job = q.read(); handle(job)`.
- **Data flow:** Bronze → silver → gold can be three SQL views or three explicit functions. They don't need to be "assets" in a registry. They need to be reproducible from inputs.
- **UI orchestration view:** A simple "recent runs" table in the BFF showed job start, end, status, duration. No GraphQL, no proxy, no alembic-on-Dagster-postgres.

This stack supported every demoable behavior MVP-A produced (training a model, running a walk-forward, gating a promotion) and would have shipped in a fraction of the surface area.

**When does Dagster (or Prefect, or Airflow) earn its keep?**

- When **multiple human teams** need a shared orchestrator UI and DAG language.
- When **lineage** must be auditable across heterogeneous assets (e.g., feature stores, multiple model families, multiple downstream consumers).
- When **scheduling complexity** exceeds cron — e.g., asset freshness policies, partial backfills, sensors waiting on external state.
- When the team is **already using it** for other workloads.

None of those applied to MVP-A. The platform had one user (you), one workload, one deployment target, and PGMQ already in the stack.

**Recommendation for the rewrite:** start with PGMQ + APScheduler + worker. Add an orchestrator only when a concrete pipeline needs one of the four properties above.

---

## What worked and should be kept (or re-evaluated, but warmly)

- **BFF + IdP federation pattern.** Two roles in the single image, IdP mints RS256 JWTs with `/jwks`, federates Google/Entra/mock, Postgres-backed sessions. The auth design held up through the rushed build and required no rework. Keep.
- **CQRS + hash-chained audit log with `pg_advisory_xact_lock`.** The lock pattern (`pg_advisory_xact_lock(0xA7D17_106)`) survived concurrent-writer race conditions that `FOR UPDATE` alone could not. Pattern is sound.
- **MLflow registry with Aliases (after F2 fix).** The right surface for promotion. Keep, but wire it up correctly the first time.
- **Walk-forward as a platform-enforced gate.** PBO + DSR + CPCV in `app/quant/validation/` is the honest-research substrate. Keep the math; rebuild the orchestration around it.
- **testcontainers for migration roundtrip testing.** F4 added one test that exercises `alembic downgrade base && alembic upgrade head`. Cheap, high-value. Keep.
- **Single-image-multi-role pattern.** One Docker image, role selected at runtime. Survives the rewrite intact.
- **Subagent-driven development.** The execution mechanism worked; the inputs (plan + scope) were what failed. Use it again, with a smaller plan.

---

## What to throw away

- **`apps/api/app/dagster_defs/`** — the entire directory. Dagster integration. Bronze/silver/gold assets. Walk-forward assets. Jobs. Sensors. Webserver. Daemon. Code-locations. All of it.
- **BFF Dagster reverse proxy** (`apps/api/app/bff/dagster_proxy.py`). No upstream to proxy.
- **API Dagster GraphQL passthrough** (`apps/api/app/api/dagster_graphql.py`). Same reason.
- **Per-strategy codegen pattern.** Already removed in F0; do not re-introduce under any abstraction.
- **The 5,840-line MVP-A plan** as a template. Plans this size are a smell.
- **The "Qlib reference workload" framing.** If we want a Qlib comparison, port a real Qlib workload. Otherwise stop name-checking it.

---

## Tech stack to re-evaluate (with pre-Dagster baseline)

| Layer | MVP-A choice | Pre-Dagster baseline | Re-evaluate? |
|---|---|---|---|
| Web framework | FastAPI + Pydantic v2 | same | Keep — no friction |
| DB | Postgres + asyncpg + SQLAlchemy + Alembic | same | Keep |
| Messaging | PGMQ | PGMQ | Keep |
| Scheduling | APScheduler + Dagster daemon | APScheduler only | **Drop Dagster daemon** |
| Orchestration UI | Dagster webserver (proxied) | "Recent runs" table in BFF | **Drop Dagster** |
| ML registry | MLflow with Aliases | MLflow with Aliases | Keep — wire correctly |
| Data | Polars (lts-cpu on dev VM) | same | Keep |
| Auth | BFF + IdP federation, RS256 + JWKS | same | Keep |
| Frontend | (not built in MVP-A) | doodle-1 stack: React 19 / Vite / TanStack Router / Tailwind v4 / Radix / Motion / Zustand / Sonner / Geist | New decision for MVP — see `memory/reference_ux_patterns.md` |
| SDK | Python skeleton in `sdk/quantplatform/` (17 tests) | — | New first-class deliverable |
| Testing | pytest + testcontainers + hypothesis | same | Keep |
| Local dev | docker-compose | same | Keep — golden rule |
| Deployment | Cloud Run + Cloud SQL + GitHub Actions | same | Keep |

**The one decision the next MVP must make explicitly:** orchestration. If the answer is "PGMQ + a worker + a recent-runs view," say so out loud and resist the upgrade for as long as humanly possible.

---

## Pointers

- **GitHub branches/tags:** `archive/mvp-a-rushed-2026-04-22`, tag `archive-mvp-a-2026-04-22` on `FreeSideNomad/quant-platform`.
- **Local archive:** `../deployment/quant-platform-archive-2026-04/` (same repo, different clone, full history).
- **Blueprint + SDK + docs tarball:** `../deployment/deployment-artifacts-2026-04.tar.gz`.
- **The architectural review that triggered the park:** in archive, `../deployment/quant-platform-archive-2026-04/STATUS.md` "Decisions in retrospect" section + the honest-hardening plan at `../deployment/docs/superpowers/plans/2026-04-22-honest-hardening.md`.
- **MVP-A plan (the smell):** `../deployment/docs/superpowers/plans/2026-04-21-mvp-a-implementation.md`.
