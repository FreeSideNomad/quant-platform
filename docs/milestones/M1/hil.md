# Milestone M1 — HIL Checkpoint

## Scope of this review

What landed:
- Monorepo skeleton (apps/api, apps/ui, apps/accounts placeholder, packages/sdk).
- `qp` CLI with `up`, `down`, `doctor` subcommands.
- `docker-compose.yml` with Postgres (pgmq) + MinIO + MLflow + FastAPI API + UI + mock OIDC, on 1xxxx host ports.
- Alembic initialized with empty initial migration (creates pgmq extension).
- FastAPI `/health` endpoint returning `{status, role, version}`.
- UI placeholder that fetches `/api/health` and renders the response.
- Integration test (`tests/integration/test_compose_stack.py`) verifying all services respond.

What did NOT land (deliberately):
- Any SDK surface beyond CLI stubs. (M3)
- Validation math. (M2)
- MLflow alias wiring. (M4)
- Serving role. (M6)
- Real authentication. (M7)
- Real UI screens. (M5)

## Prerequisites

- Repo at commit `<sha>` (latest on `main` after merge)
- Docker Desktop (or equivalent) running
- Ports 14444, 15000, 15173, 15432, 18000, 19000, 19001 free
- uv installed (`curl -LsSf https://astral.sh/uv/install.sh | sh` if missing)

Note on macOS: port 5000 is often held by Control Center (AirPlay Receiver). The M1 stack deliberately uses host port 15000 for MLflow (and 1xxxx values for every other service) so that the default macOS configuration does not conflict. If any 1xxxx port reports in-use, identify the holder with `lsof -i :<port>` and free it before continuing.

Automated tests all green:
- `uv run --group integration pytest tests/integration/ -v` → all PASS (5 tests)
- `cd apps/api && uv run pytest -v` → all PASS (health + alembic roundtrip)
- `cd packages/sdk && uv run pytest -v` → all PASS (version + up + down + doctor)

## Script

1. **Clean-clone test**
   - On a second working directory (simulates a fresh laptop). While this HIL runs *before* M1 merges to `main`, the skeleton lives on `feat/m1-skeleton`, so clone with the branch flag:
     ```bash
     git clone --branch feat/m1-skeleton git@github.com:FreeSideNomad/quant-platform.git /tmp/qp-fresh
     cd /tmp/qp-fresh
     ```
     After M1 ships (branch merged to `main`), drop `--branch feat/m1-skeleton`; the HIL can then be re-run against `main` as a regression check.
   - Expected: clone completes without errors, `git log -1` shows the latest M1 commit.

2. **Install the CLI**
   ```bash
   uv sync --all-packages
   uv run qp --version
   ```
   - Expected: prints `qp 0.1.0`.
   - Note: `--all-packages` is required because the root `pyproject.toml` is a workspace shell with no dependencies; plain `uv sync` would not install `quantplatform` (which defines the `qp` script).

3. **Run qp doctor**
   ```bash
   uv run qp doctor
   ```
   - Expected: all four checks (Docker, Compose, Python, Ports) show `OK`. If any fail, address before continuing.

4. **Bring up the stack**
   ```bash
   uv run qp up
   ```
   - Expected: terminal shows `Starting Quant Platform stack...` then `Stack started. UI at http://localhost:15173`.
   - Budget: <90 seconds on a cold laptop (image pulls included).

5. **Verify all services**
   ```bash
   docker compose ps -a
   ```
   - Expected: every long-running service row shows `healthy` (postgres, minio, mlflow, mock-oidc, api, ui). The `minio-init` row is `exited (0)` — that's correct; it's a one-shot init job. The `-a` flag is required: plain `docker compose ps` hides exited containers, so `minio-init` would be invisible without it.

6. **Hit each service in a browser or curl**
   - `http://localhost:18000/health` (curl or browser) — expect JSON `{"status":"ok","role":"api","version":"0.1.0"}`
   - `http://localhost:15000` (browser) — expect MLflow UI
   - `http://localhost:19001` (browser) — expect MinIO console (login: `minioadmin` / `minioadmin`)
   - `http://localhost:14444/.well-known/openid-configuration` (curl or browser) — expect JSON with `issuer`
   - `http://localhost:15173` (**browser only** — the UI is a client-rendered React SPA; curl returns only the HTML shell and will not show the placeholder text) — expect an `<h1>Quant Platform</h1>` heading, the caption "Skeleton (M1). Real UI ships in M5.", and a preformatted block containing the JSON `{status, role, version}` returned by `/api/health`.

7. **State-persistence test**
   - `uv run qp down` — expected: stack stops gracefully; volumes preserved
   - `docker compose ps` — expected: no running containers
   - `uv run qp up` — expected: stack returns quickly (<30s; images and volumes reused)
   - Connect to Postgres and check the `pgmq` extension persisted (use `docker exec` so no host-side `psql` client is required):
     ```bash
     docker exec qp-postgres psql -U qp -d qp -c "\dx" | grep pgmq
     ```
     Expected: a single row with `pgmq` listed. Extensions persist across `down` / `up` because the Postgres volume is preserved.

8. **`qp doctor` after boot**
   - `uv run qp doctor` — expected: some ports now show as in-use (API on 18000, UI on 15173, etc.); this is correct behavior when the stack is up. Confirm this matches spec-behavior expectations.

9. **Tear-down**
   - `uv run qp down`
   - `docker compose ps` — expected: nothing running.

## Decision points (HIL judgement)

- **Is `qp up` time acceptable?** Spec DoD says <5 minutes from clone to running stack. What did this laptop hit? Within budget?
- **Is the `qp doctor` output clear?** Does "Port 18000 already in use" when the stack is up feel correct, or should doctor distinguish "our own stack is using it" from "someone else has it"?
- **Is the UI placeholder useful, or distracting?** A placeholder reading "real UI ships in M5" sets the expectation; an empty page does not. Is the message right?
- **Does the clean-clone flow work for a Linux user as well as a Mac user?** If only tested on one, note whether the other is a risk.
- **Were the 1xxxx host ports the right call?** The port moves were made to sidestep known collisions (notably macOS Control Center holding port 5000). Revisit if any chosen port turns out to collide with something unexpected on a user's machine.

## Sign-off (2026-04-24)

- [x] Automated tests green (unit + integration): SDK 6/6, API 4/4, Integration 5/5
- [x] Script ran to completion on macOS (`/tmp/qp-fresh`) and Ubuntu 24.04 x86_64 (`igor@ubuntu-server.local:/tmp/qp-fresh`); fresh-laptop boot 22s (Mac) / 17.6s (Linux), well under the 90s budget
- [x] Decision points resolved (below)
- [x] User approves proceeding to M2 (validation math port)

### Decision-point resolutions

1. **`qp up` time acceptable** — yes. Cold 22s (Mac arm64) / 17.6s (Linux x86_64); far under the 90s plan budget and the 5-minute spec DoD.
2. **`qp doctor` output clarity** — fixed mid-HIL (commit `768fe69`). When our stack is up, the busy ports are now reported as `N port(s) held by running qp stack (expected)` with exit 0; an external collision still exits 1.
3. **UI placeholder readable** — yes, verified in Chrome: `<h1>Quant Platform</h1>`, "Skeleton (M1). Real UI ships in M5.", and the `/api/health` JSON block all render.
4. **Linux compatibility** — yes, HIL re-run on Ubuntu 24.04 x86_64 passed all 9 steps.
5. **1xxxx host ports the right call** — yes, retain. The Mac `AirPlay Receiver` collision on port 5000 proved the concern real.

## Defects found (all resolved during HIL)

All classified **MUST-FIX-BEFORE-M2** and landed on `feat/m1-skeleton` before sign-off:

| # | Finding | Fix commit |
|---|---|---|
| 1 | `uv sync` alone doesn't install workspace-member scripts on fresh clone → `qp` not on PATH | `530594b` |
| 2 | `docker compose ps` hides the `minio-init` exited(0) row → step 5 expectation unverifiable | `6a3da3e` |
| 3 | UI check via `curl` returns only the HTML shell → needs browser-only note + concrete content expectation | `6a3da3e` |
| 4 | `psql` host-side client not on every laptop → switch to `docker exec qp-postgres psql …` | `6a3da3e` |
| 5 | Pre-merge clone must use `--branch feat/m1-skeleton` (main doesn't yet have the skeleton) | `14d22c8` |
| 6 | No migrations runner in the compose stack → pgmq extension absent at boot | `3bba6fd` |
| 7 | `qp doctor` reports FAIL on ports held by our own running stack | `768fe69` |
| 8 | MLflow and the qp app share the `qp` database → their two Alembic trees collide on `alembic_version` | `0589a53` |

## Spec / plan updates triggered

- **§5.1 & compose:** host-port scheme moved from {5432, 9000, 9001, 5000, 4444, 8000, 5173} to the 1xxxx block {15432, 19000, 19001, 15000, 14444, 18000, 15173}. Driven by the macOS AirPlay Receiver port-5000 collision; generalises the hygiene to "don't bind well-known host ports for local dev stacks."
- **§6.2:** MLflow now uses a dedicated `mlflow` database inside the shared Postgres instance (not `qp`), because MLflow manages its own Alembic migration tree and the two collide on a shared `alembic_version` table. Worth adding to the spec's §6.2 schema notes so future milestones don't re-introduce the collision.
- **CLI contract:** `qp doctor` port-check now distinguishes "held by our own running stack" (OK) from "held by something external" (FAIL). The spec's CLI-surface table doesn't need to grow, but this nuance belongs in the `qp doctor` help/reference once written.
