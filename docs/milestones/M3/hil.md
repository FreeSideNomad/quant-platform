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

- Repo on `main` at the M3 merge SHA (or on `feat/m3-sdk-local-runs` pre-merge)
- Python 3.12+, `uv` installed
- Docker Desktop (or equivalent) running
- Ports 14444, 15000, 15173, 15432, 18000, 19000, 19001, 5678 free

```bash
# From a fresh clone (repo is public; `git clone https://...` also works):
git clone --branch feat/m3-sdk-local-runs git@github.com:FreeSideNomad/quant-platform.git /tmp/m3-hil
cd /tmp/m3-hil
uv tool install ./packages/sdk
pq --version          # → pq 0.2.0
```

If `uv tool install` complains `Permission denied` while symlinking to
`~/.local/bin/pq`, that directory is root-owned on your machine; fix
with `sudo chown -R $(whoami) ~/.local/bin`, then rerun the install.

## Script (target 30 min)

1. **`pq doctor`** — all four checks green (Docker, Compose, Python, Ports).

2. **`pq up`** — stack boots with all services healthy (postgres, minio, mlflow, mock-oidc, api, ui, migrations exited(0)). Budget <90s warm.

3. **`pq new strategy m3-hello`** — inspect the scaffolded tree:
   - `m3-hello/pq.toml` with `project.name = "m3-hello"`, `project.entry = "m3_hello.strategy:main"`
   - `m3-hello/src/m3_hello/strategy.py` (note underscored directory)
   - `m3-hello/tests/test_strategy.py`, `.vscode/launch.json`, `.idea/runConfigurations/`, `.pre-commit-config.yaml`, `.githooks/pre-push`, `README.md`
   - Confirm the strategy.py is under 40 lines of user-visible code.

4. **`cd m3-hello && uv sync`** — resolves `quantplatform` from the
   public GitHub repo on the `feat/m3-sdk-local-runs` branch (the
   template's ref flips to `@main` at M3-merge; switches to plain
   `"quantplatform"` PyPI dep at M8). Expect <5s on a warm cache.

5. **`pq run m3-hello`** — host-mode run. Watch the console for:
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
   pq run m3-hello --container --debug
   ```
   In VS Code: "Debug strategy (container)" launch config → click attach → strategy subprocess breaks at the first line inside `main()`. Step through a few lines to confirm.
   If VS Code debug attach fails, fall back to verifying debugpy is listening: `curl -v http://localhost:5678` should get a connection (the protocol isn't HTTP, but the TCP handshake will complete).

9. **`pq e2e m3-hello`** — runs ruff check + format + pyright (best-effort) + pytest + `pq run --container`. Should exit 0 under 90s on a warm run. Reports a summary table.

## Decision points (HIL judgement)

- **Is the hello-world strategy template under 40 lines as spec commits?** Count user-visible code in `src/m3_hello/strategy.py` (not imports, not docstring).
- **Are the MLflow log keys and event payloads legible?** Open one MLflow run + one `events.payload` JSON and judge: would a new developer reading these understand what happened?
- **Does the debugger attach flow work cleanly in at least one IDE?** VS Code is primary; PyCharm configs are scaffolded but not validated in this HIL.
- **Is the 90s `pq e2e` budget actually hit on first vs warm run?** Record the times. If warm >90s, flag as a spec concern.
- **Is the scaffolded project's first `uv sync` reasonable for a quant new to the stack, given the current patch-the-pyproject workaround?** If "no" — that's a MUST-FIX-BEFORE-M4 because M4 will layer more user-facing scaffolding on top.

## Pre-HIL fixes already landed (2026-04-24)

Three scaffolding defects surfaced during the pre-HIL critical review
were fixed on the branch before this sign-off:

| # | Finding | Fix commit |
|---|---|---|
| 1 | Template dir `src/{{name}}/` kept hyphens; strategy.py imports required underscores | `cad17b5` (dir renamed to `src/{{ name.replace("-", "_") }}/`) |
| 2 | Scaffolded pyproject declared `"quantplatform"` PyPI dep → failed to resolve pre-M8 | `cad17b5` (switched to `quantplatform @ git+https://...`); repo made public so no auth is needed; `0937384` pinned the ref at the feature branch until M3 merges to main |
| 3 | `mlflow-skinny` unpinned → resolved to 3.x, incompatible with compose's MLflow 2.16 | `cad17b5` (pinned `>=2.16,<3.0` in SDK prod deps) |
| 4 | Scaffolded `strategy.py` / `test_strategy.py` failed `ruff format --check` → `pq e2e` fatal | `d9a53fc` (reformatted both templates to ruff-canonical layout); SDK version bumped 0.1.0 → 0.2.0 so fresh `uv tool install` picks up the update |

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
