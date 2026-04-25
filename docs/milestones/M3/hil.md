# Milestone M3 — HIL Checkpoint

## Scope of this review

What landed:
- `quantplatform.sdk` module with `Strategy` base class, `data.ohlcv`, `run.start` context manager, hash-chained audit log (ported from MVP-A archive), content-hashed lineage writes.
- `pq new strategy <name>` scaffolds the hello-world-vol-har template.
- `pq run <name>` executes a strategy locally (host mode) with strategy upsert via API.
- `pq run --container` runs the strategy inside the worker container with optional `debugpy` attach.
- `pq e2e` pre-push hook: ruff + pyright + pytest + container run.
- Alembic migration 0002_m3_schema with six tables (strategies, runs, events, datasets, dataset_versions, lineage_reads).
- Bundled synthetic SPY-labelled daily OHLCV parquet (~125 KB, seed=20260424) registered as dataset `ohlcv-spy-daily-synthetic/v1`.
- Dev-clone install hygiene (`uv tool install ./packages/sdk` → `pq` on PATH) documented in `docs/INSTALL.md`.
- End-to-end integration test `tests/integration/test_pq_run_hello_world.py` — passes in ~47s warm.

What did NOT land (deliberately):
- Promotion gate wiring into runs (M4).
- `POST /models/<name>/versions/<v>/promote` API (M4).
- Walk-forward chart / Run detail UI (M5).
- `hello-world-returns` companion template expected to fail the gate (M4 — the gate has to exist for the fail path to be meaningful).
- Serving role and inference (M6).
- Real authentication (M7).
- PyPI publish, `curl | sh` install endpoint (M8).

## Prerequisites

- Python 3.12+
- Docker Desktop (or equivalent) running
- Ports 14444, 15000, 15173, 15432, 18000, 19000, 19001, 5678 free
- Network access to GitHub + `pyquant.io`

## Install

One command. Self-contained — installs uv (if missing), clones the
platform into `~/.pq/platform`, installs `pq` from that clone, runs
`pq init` automatically. Re-running upgrades to latest `main`.

```bash
curl -fsSL https://pyquant.io/install.sh | bash       # macOS / Linux
irm   https://pyquant.io/install.ps1 | iex            # Windows
```

Expected output: a single green line.

```
✔ pq 0.3.0 installed.          # fresh install
✔ pq 0.2.0 upgraded to 0.3.0.  # if you had a prior install
```

Detail (clone, uv tool install, pq init) is appended to
`~/.pq/logs/install.log` for diagnosis if the line above is red.

If `uv tool install` errors with `Permission denied` symlinking to
`~/.local/bin/pq`, that directory is root-owned on your machine; fix
with `sudo chown -R $(whoami) ~/.local/bin`, then re-run the installer.

### Testing-policy note

Until M-something-late ships, `https://pyquant.io/install.sh` always
points at HEAD of `main`. We keep `main` honest by running HIL against
it directly — anything that breaks `main` is fixed forward, no
release branch.

After v1 ships and real users depend on `install.sh`, the HIL endpoint
moves to `https://pyquant.io/install-test.sh` (which tracks a
`pre-release` branch or similar), and `install.sh` only flips to that
branch's tip after sign-off.

## Script (target 30 min)

1. **`pq doctor`** — all four checks green (Docker, Compose, Python, Ports).

2. **`pq up`** — stack boots with all services healthy (postgres, minio,
   mlflow, mock-oidc, api, ui; migrations exited(0)). Quiet by default;
   detail goes to `~/.pq/logs/up-<ts>.log`. Budget <90s warm. Expected
   one-line output: `✔ Stack started.` (or `✔ Stack already running.`).

3. **`cd /tmp && pq new m3-hello`** (any cwd — `pq new` doesn't depend
   on the platform repo). Inspect the scaffolded tree:
   - `m3-hello/pq.toml` with `project.name = "m3-hello"`, `project.entry = "m3_hello.strategy:main"`
   - `m3-hello/src/m3_hello/strategy.py` (note underscored directory)
   - `m3-hello/tests/test_strategy.py`, `.vscode/launch.json`, `.idea/runConfigurations/`, `.pre-commit-config.yaml`, `.githooks/pre-push`, `README.md`
   - Confirm the strategy.py is under 40 lines of user-visible code.

4. **`cd m3-hello && uv sync`** — resolves `quantplatform` from
   `git+https://github.com/FreeSideNomad/quant-platform.git@main` and
   pins it in the project's `uv.lock`. Expect <5s on a warm cache.

5. **`pq run`** — host-mode run from inside the project dir (no
   positional needed; `pq.toml` in cwd identifies the project, dotnet/
   cargo style). Watch the console for:
   - `Upserting strategy 'm3-hello'...` → `Strategy created: m3-hello (<prefix>)`
   - Subprocess logs: walk-forward folds, LightGBM training
   - `Strategy completed successfully.`

6. **MLflow UI** — open http://localhost:15000. Find:
   - Experiment `quant-platform/m3-hello`
   - A run with logged metrics `fold_0_rmse` … `fold_N_rmse`, `mean_rmse`, `std_rmse`
   - A registered pyfunc model artifact at `model/`

7. **Postgres inspection**:
   ```bash
   docker exec pq-postgres psql -U qp -d qp -c \
     "SELECT run_id, dataset_version_id, rows_returned FROM lineage_reads ORDER BY id DESC LIMIT 5;"
   docker exec pq-postgres psql -U qp -d qp -c \
     "SELECT event_type, encode(prev_hash,'hex') AS prev, encode(this_hash,'hex') AS this, created_at FROM events WHERE run_id IS NOT NULL ORDER BY created_at DESC LIMIT 10;"
   ```
   Verify:
   - At least one `lineage_reads` row for the run
   - Event chain contains `RunStarted`, `DataRead`, `ModelTrained`, `RunFinished` in that order
   - Every event's `prev_hash` equals the previous event's `this_hash` (audit chain intact)

8. **Debugger attach (container mode)**:
   ```bash
   pq run --container --debug
   ```
   In VS Code: "Debug strategy (container)" launch config → click attach → strategy subprocess breaks at the first line inside `main()`. Step through a few lines to confirm.
   If VS Code debug attach fails, fall back to verifying debugpy is listening: `curl -v http://localhost:5678` should get a connection (the protocol isn't HTTP, but the TCP handshake will complete).

9. **`pq e2e`** — runs ruff check + format + pyright (best-effort) + pytest + `pq run --container`. Should exit 0 under 90s on a warm run. Reports a summary table.

## Decision points (HIL judgement)

- **Is the hello-world strategy template under 40 lines as spec commits?** Count user-visible code in `src/m3_hello/strategy.py` (not imports, not docstring).
- **Are the MLflow log keys and event payloads legible?** Open one MLflow run + one `events.payload` JSON and judge: would a new developer reading these understand what happened?
- **Does the debugger attach flow work cleanly in at least one IDE?** VS Code is primary; PyCharm configs are scaffolded but not validated in this HIL.
- **Is the 90s `pq e2e` budget actually hit on first vs warm run?** Record the times. If warm >90s, flag as a spec concern.
- **Is the scaffolded project's first `uv sync` reasonable for a quant new to the stack?** The scaffold now resolves `quantplatform` straight from the public GitHub repo with no hand-editing — timing should be <5s on warm cache, <30s cold. Flag if the UX feels wrong for a first-time quant.

## v0.4.0 upgrade notes (2026-04-25)

Three substantive changes between 0.3.4 and 0.4.0 — coordinated because
they all want a fresh stack volume:

1. **MLflow 2.16 → 3.11.** Server image (`compose/mlflow/Dockerfile`)
   bumped to `ghcr.io/mlflow/mlflow:v3.11.1`; client `mlflow-skinny`
   pinned `>=3.11,<4.0`. Eliminates the pydantic / utcnow / type-hint
   deprecation warnings that came from 2.x's own internals — see
   [MLflow #11203](https://github.com/mlflow/mlflow/issues/11203). The
   `log_model` call is now `name=` (was `artifact_path=`); model URI
   format is `models:/<model_id>` (we use the returned object's
   `.model_uri` attribute, not a hand-built string).

2. **Migrations collapsed `0001_init` + `0002_m3_schema` → `0001_v1`.**
   Single baseline. `alembic_version` rows from the old multi-step
   history are incompatible — which is why a fresh volume is required.

3. **Bundled dataset replaced** — synthetic `spy_daily.parquet` →
   real `aapl_daily.parquet`. Source: [jacksoncrow/stock-market-dataset
   on Kaggle](https://www.kaggle.com/datasets/jacksoncrow/stock-market-dataset),
   CC0 Public Domain. 9,909 daily bars, 1980-12-12 → 2020-04-01. See
   `apps/api/data/PROVENANCE.md`. The v1 migration derives `content_hash`
   and `schema_json` from the parquet bytes at upgrade time — no
   hard-coded literals, structurally drift-free. `data.ohlcv()` now
   takes `ticker="AAPL"` instead of `"SPY"`.

**Required HIL prep step before re-running:**

```bash
pq down -v   # removes both qp-postgres-data and qp-minio-data volumes
pq up        # rebuilds images (--build is default), runs the v1
             # migration fresh, re-uploads the new aapl_daily.parquet
             # to MinIO, MLflow 3.x initialises its own backend store
```

The bundled parquet ships in the repo. If a maintainer needs to
refresh it (new ticker, license re-verification), run
`uv run python scripts/refresh_aapl_data.py` with `KAGGLE_API_TOKEN`
exported in the shell — end users never need a Kaggle account.

## Corrections to recent commit explanations (2026-04-25)

A code review on 2026-04-25 caught two commit messages that mis-stated
what the underlying defect was. Recording the actual technical reasons
here so they don't rot in git history:

**`18942bd` (v0.3.1)** — "pass DataFrames into LightGBM .fit/.predict
to drop sklearn warning". The commit said the lightgbm sklearn wrapper
"captured names from the polars DataFrame's column metadata via some
path in lightgbm 4.x's input handling." That is wrong. LightGBM never
sees polars metadata. What actually happens: even with `numpy` arrays
on both sides, `LGBMRegressor.fit(X)` synthesizes `Column_0..N` names
and sets `feature_names_in_` from them; `LGBMRegressor.predict(X)`
then triggers sklearn's `_check_feature_names` which warns because the
predict numpy array has no names to match. Going through pandas (with
real column names from the polars schema) is the correct fix; it also
gives the saved model real feature names instead of `Column_N`.

**`cc6de01` (v0.3.2)** — "drop pyfunc type hint to silence MLflow
warning". The commit framed this as silencing a yellow warning. It
was actually silencing a hard `MlflowException`: MLflow 2.22's
`_get_func_info_if_type_hint_supported` raises when the hint isn't
`list[<DataFrame>]`. Removing the hint is one valid path, but the
proper long-term shape is `model_input: list[pl.DataFrame]` with the
implementation unwrapping `model_input[0]` — that's what M6 serving
will assume when fanning out batched inference. Done in v0.3.3.

**`cc6de01` AWS_*/MLFLOW_S3 injection** — silently overrode any
pre-existing `AWS_ACCESS_KEY_ID` in the user's shell with `minioadmin`.
Functionally correct (the strategy subprocess must talk to MinIO, not
real AWS) but no warning, no documented surface. v0.3.3 moves the
translation into the SDK (`apply_mlflow_s3_env()` in `sdk/_config.py`):
public surface is `PQ_S3_*` only, and the shim logs a warning when it
shadows a non-matching pre-existing AWS_* value. The CLI's
`PLATFORM_ENV` no longer carries any AWS_* keys.

**`9085e49` `pq up`** — quieted to one line, but the underlying
`docker compose up -d` returns success on container creation, not on
healthcheck pass. `pq run` would then fail in confusing ways if a
service was still flapping. v0.3.3 adds `--wait` so the success
message only fires after every health-checked service is healthy.

## CLI UX overhaul (2026-04-23)

Triggered by feedback during the in-progress HIL run. Behaviour changes:

| What | Before | After |
|---|---|---|
| Scaffold | `pq new strategy hello-world` | `pq new hello-world` (`--template hello-world` is the default; the `strategy` subgroup is gone) |
| Run | `pq run hello-world` from outside the project | `pq run` from inside the project (cwd's `pq.toml` identifies the project, dotnet/cargo style); positional name still accepted for back-compat |
| Stack up | streams docker compose to terminal | quiet by default; detail in `~/.pq/logs/up-<ts>.log`; pass `--verbose` to stream |
| Installer | streams clone + uv tool install | quiet; detail in `~/.pq/logs/install.log`; only the version line goes to terminal |
| SDK env vars | `DATABASE_URL`, `S3_*`, `MLFLOW_TRACKING_URI`, `QP_STRATEGY_ID`, `QP_AS_OF`, `QP_API_URL`, `QP_PLATFORM_DIR` | `PQ_*` prefix on all of them. `pq run` injects canonical `PQ_*` host URLs into the strategy subprocess so the user doesn't have to set anything; user-set `PQ_*` overrides. Worker container's docker-compose env is updated to match. |
| SDK version | 0.2.0 | 0.3.0 (breaking CLI + env-var change) |

The DATABASE_URL clash that triggered the rename: the strategy subprocess
read `DATABASE_URL` from the user's shell, but on a real laptop that env
is often already set for an unrelated project (e.g. SQLAlchemy app), and
the rogue value broke the SDK. PQ-prefixed names are unique to this
platform, so they don't collide with anything else the user has running.

## Pre-HIL fixes already landed (2026-04-24, 2026-04-25)

Defects surfaced during the pre-HIL critical review were fixed on
`main` before this sign-off:

| # | Finding | Fix commit |
|---|---|---|
| 1 | Template dir `src/{{name}}/` kept hyphens; strategy.py imports required underscores | `cad17b5` (dir renamed to `src/{{ name.replace("-", "_") }}/`) |
| 2 | Scaffolded pyproject declared `"quantplatform"` PyPI dep → failed to resolve pre-M8 | `cad17b5` (switched to `quantplatform @ git+https://...`); repo made public so no auth is needed; `0937384` pinned the ref at the feature branch until M3 merges to main |
| 3 | `mlflow-skinny` unpinned → resolved to 3.x, incompatible with compose's MLflow 2.16 | `cad17b5` (pinned `>=2.16,<3.0` in SDK prod deps) |
| 4 | Scaffolded `strategy.py` / `test_strategy.py` failed `ruff format --check` → `pq e2e` fatal | `d9a53fc` (reformatted both templates to ruff-canonical layout); SDK version bumped 0.1.0 → 0.2.0 so fresh `uv tool install` picks up the update |
| 5 | `pq --version` reported `0.1.0` after the pyproject bump — Python `__version__` was out of sync | `12b3d9f` aligns `quantplatform.__version__` with the pyproject version |
| 6 | `dataset_versions.content_hash` stuck at zero placeholder | `47cd059` migration hard-codes the bundled parquet's xxh64 + new test_bundled_dataset.py guards drift |
| 7 | `pq up` cached old api image → migration changes didn't land | `12756f4` adds `--build` by default; `--no-build` opts out |
| 8 | `pq doctor` from non-platform cwd reported false-FAIL on busy ports | `2bd0aad` detects stack via `docker ps --filter name=pq-` instead of `docker compose ps -q` |
| 9 | `pq up` cross-clone container_name conflicts (`/pq-mock-oidc` already in use) | `e35d868` sweeps stopped pq-* orphans before compose up |
| 10 | `pq up` / `pq down` / `pq run --container` required cwd to be the platform repo root | `fc2bfac` ships `pq init` + `~/.pq/config.toml`; commands resolve via `require_platform_dir()` |
| 11 | Install was multi-step (clone, `uv tool install`, `pq init`) | pyquant-site `b88e28e` ships self-contained `install.sh` / `install.ps1` that does all three |

## Non-fatal warnings you will see (acceptable for M3)

These are cosmetic and not sign-off blockers; flag any you want ticketed:

- **sklearn: "X does not have valid feature names, but LGBMRegressor was fitted with feature names"** — emitted per fold by the LGBM prediction path. The features DataFrame has named columns on fit; prediction goes through a NumPy array without names. Fixable by passing the DataFrame (not `.to_numpy()`) to `.predict()` in `Strategy.train_and_validate`, or by suppressing via `warnings.filterwarnings` inside the strategy wrapper.
- **MLflow: "Type hints must be wrapped in list[...]"** — the pyfunc wrapper's `predict(self, context, model_input)` uses `pl.DataFrame` as the input type hint; MLflow wants `list[pl.DataFrame]`. Cosmetic.
- **MLflow: "requirements_utils: The following packages were not found in the public PyPI package index: {'quantplatform'}"** — expected pre-M8; MLflow's conda-env capture can't find quantplatform on PyPI because it isn't there yet. Resolves naturally at M8.

## Sign-off

- [ ] Automated tests green — SDK unit (90), API (8), E2E integration (1).
- [ ] `pq doctor` / `pq up` / `pq new` / `pq run` / `pq e2e` all exit 0 on this machine.
- [ ] MLflow and Postgres inspection steps confirm the run shape is correct.
- [ ] Debugger attach worked in at least one IDE.
- [ ] Decision points resolved (see notes).
- [ ] User approves proceeding to M4 (gate wiring + promote API).

## Defects found

(Add below; classify each as MUST-FIX-BEFORE-M4 / DEFER-TO-V2 / SPEC-UPDATE)

The four pre-HIL defects in the table above are all fixed on-branch.
This section is for anything HIL surfaces on top of that.

## Spec / plan updates triggered

(If a scope commitment changes — e.g., bringing PyPI publish forward, renaming the CLI again, dropping the `pq new` scaffold in favor of a git template — record it here.)

## Open design question carried forward to M4

**`Strategy.additional_gates: list[Gate]`** — extensibility bolt-on for custom tenant gates on top of the mandatory PBO/DSR/CPCV triple. Flagged during M2 HIL. Revisit during M4 planning when the gate gets wired.
