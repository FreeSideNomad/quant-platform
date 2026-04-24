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

## Sign-off

- [ ] Automated tests green (unit + integration)
- [ ] Script ran to completion without surprises
- [ ] Decision points resolved (see notes below)
- [ ] User approves proceeding to M2 (validation math port)

## Defects found

(Add below; classify each as MUST-FIX-BEFORE-M2 / DEFER-TO-V2 / SPEC-UPDATE)

## Spec / plan updates triggered

(If any finding changes a commitment in the spec or the M2 plan, record it here.)
