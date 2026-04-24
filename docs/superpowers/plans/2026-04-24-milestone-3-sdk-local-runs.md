# Milestone 3 — SDK + Local Runs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the minimum SDK a quant needs to write, scaffold, and execute a first strategy locally — a `Strategy` base class, `sdk.data.ohlcv` with content-hashed lineage, `sdk.run` for run lifecycle, `pq new strategy <name>` scaffolding, `pq run <strategy>` host-mode execution that trains a LightGBM model, packs it as an MLflow pyfunc, and writes `runs` + `events` + `lineage_reads` rows. **No gate wiring in this milestone** — runs finish unconditionally; the M2 validation math is available but not invoked. M4 wires the gate.

**Architecture:** The SDK lives under `packages/sdk/src/quantplatform/sdk/` (parallel to `validation/` and `cli/`). Strategy entry points are user-authored Python modules executed as subprocesses (host mode) or inside the worker container (`--container` mode) — no codegen, no strategy-to-disk writes by the platform (LESSONS.md §"core mistake"). Lineage is enforced by making `sdk.data.*` the only sanctioned data access; non-SDK reads will be flagged in M4+. The audit log is hash-chained with `pg_advisory_xact_lock(0xA7D17_106)` ported from the MVP-A archive (spec decision #13).

**Tech Stack:** Python 3.12, polars-lts-cpu (already a dep), LightGBM, MLflow client, asyncpg + SQLAlchemy 2 async, Jinja2 (for the scaffold), typer (already), debugpy (for container-attach), xxhash (for content hashing), pyfunc (MLflow built-in).

**Milestone DoD (from spec §9 M3):** "Local run loop complete. Lineage works. Debugger attach confirmed. Container e2e passes."

**Scope boundaries:**
- In scope: Strategy base class (training + pyfunc pack + MLflow log; no gate); `sdk.data.ohlcv` with content hashing + `lineage_reads` writes; `sdk.run` lifecycle + event emission; audit-log hash-chain ported from archive; Alembic migration for the M3 schema; `pq new strategy` scaffolding with hello-world-vol-har template; `pq run <name>` host mode; `pq run --container` mode with debugpy; `pq e2e` pre-push hook (container build + run ≤ 90s); install hygiene (`uv tool install ./packages/sdk` → `pq` on PATH).
- Out of scope for M3: gate wiring (M4), promote API (M4), UI chart of walk-forward results (M5), `pq promote` (UI-only per spec), serving role (M6), accounts service (M7), PyPI publish + install.sh (M8).
- Open design question flagged for M4: `Strategy.additional_gates: list[Gate]` extensibility — lets tenants AND extra checks onto the mandatory PBO/DSR/CPCV three. Not built here; captured so M4 planning has it on the table.

---

## Reference inputs (archive)

The MVP-A archive at `../deployment/quant-platform-archive-2026-04/` ref `origin/archive/mvp-a-rushed-2026-04-22` contains port-ready material:

- `apps/api/app/audit/log.py` — hash-chained audit log with `pg_advisory_xact_lock(0xA7D17_106)` (spec decision 13, LESSONS.md §worth-keeping).
- `apps/api/migrations/versions/0005_audit_log.py` — audit table migration.
- `apps/api/migrations/versions/0006_strategies.py` — strategies table.
- `apps/api/migrations/versions/0003_quant_tables.py` — runs + related tables.
- `apps/api/tests/test_audit_log*.py` — audit-log tests, including concurrent-writer property tests.

We do **not** port:
- `apps/api/app/dagster_defs/*` — Dagster is out of scope (LESSONS.md §core mistake).
- The per-strategy codegen under `app/api/commands.py` (RCE-shaped via `_slugify()`; LESSONS.md §failures #1).

Everything else is built fresh.

---

## Target file structure (created/modified by this milestone)

```
quant-platform/
├── packages/sdk/
│   ├── pyproject.toml                           # MODIFIED: add lightgbm/mlflow/jinja2/xxhash/debugpy
│   ├── src/quantplatform/
│   │   ├── cli/
│   │   │   ├── main.py                          # MODIFIED: register `pq new`, `pq run`, `pq e2e`
│   │   │   ├── new_strategy.py                  # NEW: `pq new strategy <name>`
│   │   │   ├── run.py                           # NEW: `pq run <name>` (host + --container)
│   │   │   └── e2e.py                           # NEW: `pq e2e` pre-push hook
│   │   ├── sdk/
│   │   │   ├── __init__.py                      # NEW: re-exports (Strategy, data, run)
│   │   │   ├── data.py                          # NEW: `data.ohlcv(...)` + content hashing
│   │   │   ├── lineage.py                       # NEW: `lineage_reads` writer
│   │   │   ├── audit.py                         # PORTED from archive app/audit/log.py
│   │   │   ├── run.py                           # NEW: run lifecycle + event emission
│   │   │   └── strategy.py                      # NEW: Strategy base + train_and_validate()
│   │   └── templates/
│   │       └── hello-world-vol-har/             # NEW: Jinja source tree for `pq new`
│   │           ├── src/{{name}}/strategy.py.j2
│   │           ├── tests/test_strategy.py.j2
│   │           ├── pq.toml.j2
│   │           ├── pyproject.toml.j2
│   │           ├── .vscode/launch.json.j2
│   │           ├── .vscode/settings.json.j2
│   │           ├── .idea/runConfigurations/Debug_host.xml.j2
│   │           ├── .idea/runConfigurations/Debug_container.xml.j2
│   │           ├── .githooks/pre-push
│   │           └── README.md.j2
│   └── tests/
│       ├── sdk/
│       │   ├── test_data_ohlcv.py               # NEW
│       │   ├── test_lineage.py                  # NEW
│       │   ├── test_audit_log.py                # PORTED from archive
│       │   ├── test_audit_log_concurrency.py    # PORTED (hypothesis property test)
│       │   ├── test_run.py                      # NEW
│       │   └── test_strategy.py                 # NEW
│       └── cli/
│           ├── test_cli_new_strategy.py         # NEW
│           └── test_cli_run.py                  # NEW
├── apps/api/
│   ├── migrations/versions/
│   │   └── 0002_m3_schema.py                    # NEW: strategies + runs + events + datasets + dataset_versions + lineage_reads
│   └── data/
│       └── spy_daily.parquet                    # NEW: bundled 10-year SPY OHLCV (~30 KB)
├── tests/integration/
│   └── test_pq_run_hello_world.py               # NEW: full stack run
├── docs/
│   ├── milestones/M3/hil.md                     # NEW
│   └── INSTALL.md                               # NEW: `uv tool install` quickstart
└── .github/workflows/ci.yml                     # MODIFIED: run sdk/ tests; pq e2e on main
```

---

## Task 1: SDK dependencies for M3

**Files:** Modify `packages/sdk/pyproject.toml`.

- [ ] **Step 1:** Append to prod `dependencies`:
```toml
  "lightgbm>=4.5",
  "mlflow-skinny>=2.16",
  "jinja2>=3.1",
  "xxhash>=3.5",
```
`mlflow-skinny` is the lightweight client (no server deps); the compose-stack mlflow server already runs. `xxhash` is faster than hashlib's sha256 for content hashing of parquet bytes.

- [ ] **Step 2:** Append to dev deps:
```toml
  "debugpy>=1.8",
```
For host-mode `--debug` and template IDE configs.

- [ ] **Step 3:** Resolve lockfile and commit.
```bash
cd packages/sdk && uv lock
cd /Users/igormusic/code/quant-platform
git add packages/sdk/pyproject.toml uv.lock
git commit -m "feat(M3-1): SDK deps (lightgbm, mlflow-skinny, jinja2, xxhash, debugpy)"
```
Include Co-Authored-By trailer. No tests in this task.

---

## Task 2: Alembic migration for M3 schema

**Files:** Create `apps/api/migrations/versions/0002_m3_schema.py`.

Tables to create (per spec §6.2 + §7.1):
- `strategies` — `(id, name UNIQUE, owner, thresholds JSONB, git_sha, created_at)`
- `runs` — `(id, strategy_id FK, as_of DATE, status, git_sha, uv_lock_hash, started_at, finished_at)`
- `events` — `(id, event_type, payload JSONB, prev_hash BYTEA, this_hash BYTEA, created_at)` with partial UNIQUE index on `(this_hash)` and a non-null FK from events to runs only when the event is run-scoped (nullable `run_id`)
- `datasets` — `(id, name UNIQUE, description, schema_json JSONB, content_hash_scheme)`
- `dataset_versions` — `(id, dataset_id FK, version_tag, storage_uri, content_hash BYTEA, schema_json JSONB, effective_at TIMESTAMPTZ)` with UNIQUE `(dataset_id, version_tag)`
- `lineage_reads` — `(id, run_id FK, dataset_version_id FK, as_of DATE, filter_predicates JSONB, content_hash BYTEA, read_timestamp TIMESTAMPTZ, rows_returned BIGINT)`

- [ ] **Step 1:** Write the migration. Use `op.execute` for any GIN index on JSONB columns. `upgrade()` creates all 6 tables with the listed columns. `downgrade()` drops them in reverse FK order.

- [ ] **Step 2:** Extend `apps/api/tests/test_alembic_roundtrip.py` (already ported from MVP-A pattern in M1) so the existing `test_alembic_upgrade_head` / `test_alembic_downgrade_base_then_upgrade_head` pair now also exercises this new revision. The existing test launches a testcontainers pg16-pgmq and runs `alembic upgrade head`; it will pick up 0002 automatically. Add an additional assertion that verifies the `strategies` and `lineage_reads` tables exist after `upgrade head`:

```python
def test_m3_tables_created_by_head(postgres_container) -> None:
    db_url = postgres_container.get_connection_url()
    _run_alembic(["upgrade", "head"], db_url)
    import psycopg2
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = {r[0] for r in cur.fetchall()}
    conn.close()
    assert {"strategies", "runs", "events", "datasets", "dataset_versions", "lineage_reads"}.issubset(tables)
```

- [ ] **Step 3:** Run tests and commit.
```bash
cd apps/api && uv run pytest tests/test_alembic_roundtrip.py -v
# Expect: 3 tests pass (upgrade, downgrade-upgrade, m3-tables-created)
```
Commit as `feat(M3-2): alembic migration for M3 schema (strategies, runs, events, datasets, dataset_versions, lineage_reads)`.

---

## Task 3: Bundle SPY OHLCV data + dataset registration

**Files:**
- Create: `apps/api/data/spy_daily.parquet` (10-year SPY daily OHLCV ~30 KB).
- Modify: `apps/api/migrations/versions/0002_m3_schema.py` — append data-seeding block that inserts one row into `datasets` (name=`ohlcv-spy-daily`) and one row into `dataset_versions` pointing at the parquet in MinIO.

- [ ] **Step 1:** Generate the parquet locally. Use yfinance or a pre-bundled CSV — a small Python script that fetches SPY daily bars for the last 10 years, writes `open/high/low/close/adj_close/volume/date` to `apps/api/data/spy_daily.parquet` with polars. Commit the parquet binary (it's tiny, ~30 KB). For HIL reproducibility, pin the exact fetch date and asset class. Keep the script under `scripts/bundle_spy_data.py` so it can be re-run to refresh.

- [ ] **Step 2:** On first compose boot, the `minio-init` one-shot service (already in `docker-compose.yml` from M1) currently creates the `qp-artifacts` and `mlflow-artifacts` buckets. Extend it to also upload `apps/api/data/spy_daily.parquet` to the `qp-artifacts` bucket at key `datasets/ohlcv-spy-daily/v1/spy_daily.parquet`. Edit the `entrypoint:` shell block in `docker-compose.yml`:

```yaml
    entrypoint: >
      /bin/sh -c "
      mc alias set qp http://minio:9000 ${S3_ACCESS_KEY:-minioadmin} ${S3_SECRET_KEY:-minioadmin} &&
      mc mb -p qp/${S3_BUCKET_DEFAULT:-qp-artifacts} &&
      mc mb -p qp/mlflow-artifacts &&
      mc cp /bundled-data/spy_daily.parquet qp/${S3_BUCKET_DEFAULT:-qp-artifacts}/datasets/ohlcv-spy-daily/v1/ &&
      exit 0
      "
```
Add a volume mount so the container can read the parquet:
```yaml
    volumes:
      - ./apps/api/data:/bundled-data:ro
```

- [ ] **Step 3:** In migration 0002, append the dataset/dataset_version seed rows:
```python
op.execute("""
  INSERT INTO datasets (name, description, schema_json, content_hash_scheme)
  VALUES ('ohlcv-spy-daily',
          'SPY daily OHLCV bars bundled with the MVP demo',
          '{"columns": ["date", "open", "high", "low", "close", "adj_close", "volume"]}',
          'xxh64')
  ON CONFLICT (name) DO NOTHING;
""")
op.execute("""
  INSERT INTO dataset_versions (dataset_id, version_tag, storage_uri, content_hash, schema_json, effective_at)
  SELECT d.id, 'v1', 's3://qp-artifacts/datasets/ohlcv-spy-daily/v1/spy_daily.parquet',
         '\\\\x0000000000000000'::bytea, '{}'::jsonb, NOW()
  FROM datasets d WHERE d.name = 'ohlcv-spy-daily'
  ON CONFLICT DO NOTHING;
""")
```
The placeholder `content_hash` is filled in by T4's lineage-write path on first successful data read (since computing xxhash during migration would require downloading from MinIO which isn't available during alembic run).

- [ ] **Step 4:** Run integration test from M1 (`tests/integration/test_compose_stack.py`) to confirm nothing regressed. Commit as `feat(M3-3): bundle 10y SPY daily OHLCV + dataset registration`.

---

## Task 4: `sdk.data.ohlcv` with content hashing + lineage

**Files:**
- Create: `packages/sdk/src/quantplatform/sdk/__init__.py` (re-exports)
- Create: `packages/sdk/src/quantplatform/sdk/data.py`
- Create: `packages/sdk/src/quantplatform/sdk/lineage.py`
- Create: `packages/sdk/tests/sdk/__init__.py` (empty sentinel)
- Create: `packages/sdk/tests/sdk/test_data_ohlcv.py`
- Create: `packages/sdk/tests/sdk/test_lineage.py`

Public contract (per spec §6.1.1):
```python
import polars as pl
from quantplatform.sdk import data

df: pl.DataFrame = data.ohlcv(ticker="SPY", as_of=None)  # polars DataFrame
```

Internals:
- `data.ohlcv(...)` reads the parquet from MinIO (via boto3 / s3fs), filters by `_knowable_at <= as_of` if bi-temporal columns exist (graceful skip if they don't — MVP), computes content hash (xxh64 of raw bytes read), writes a `lineage_reads` row with `(run_id, dataset_version_id, as_of, filter_predicates, content_hash, read_timestamp, rows_returned)`, returns the polars DataFrame.
- `run_id` is taken from `quantplatform.sdk.run.current_run_id()` — a contextvar set by `sdk.run.start()`. If no run is active, `data.ohlcv` raises `RuntimeError("data access outside of sdk.run context")` to enforce lineage.
- `dataset_version_id` is resolved by `(dataset_name, version_tag)` lookup in Postgres.

- [ ] **Step 1:** Write `lineage.py`:
```python
"""Lineage writer: every sdk.data.* call lands a row in `lineage_reads`."""
from __future__ import annotations
from datetime import date, datetime
from typing import Any
import xxhash
from quantplatform.sdk._db import execute  # see note below


def compute_content_hash(raw_bytes: bytes) -> bytes:
    """xxh64 of the raw parquet bytes. Deterministic across platforms."""
    return xxhash.xxh64(raw_bytes).digest()


def record_read(
    *,
    run_id: str,
    dataset_version_id: str,
    as_of: date | None,
    filter_predicates: dict[str, Any],
    content_hash: bytes,
    rows_returned: int,
) -> None:
    """Insert a lineage_reads row atomically with an audit-log event."""
    # Transactional: lineage_reads INSERT + events INSERT under the advisory lock
    # (ensures the event's hash-chain and the lineage row commit together).
    execute(
        """
        WITH lin AS (
          INSERT INTO lineage_reads
            (run_id, dataset_version_id, as_of, filter_predicates,
             content_hash, read_timestamp, rows_returned)
          VALUES (:run_id, :dv_id, :as_of, :preds::jsonb, :ch, NOW(), :rows)
          RETURNING id
        )
        SELECT id FROM lin;
        """,
        run_id=run_id, dv_id=dataset_version_id, as_of=as_of,
        preds=filter_predicates, ch=content_hash, rows=rows_returned,
    )
    # Emit DataRead event on the audit chain (hash-chain handled by audit module)
    from quantplatform.sdk.audit import emit_event
    emit_event(run_id=run_id, event_type="DataRead",
               payload={"dataset_version_id": str(dataset_version_id),
                        "content_hash": content_hash.hex(),
                        "rows_returned": rows_returned})
```

Note: `quantplatform.sdk._db.execute` is a tiny synchronous helper that opens an asyncpg connection, runs the statement with named params, and closes. Keep it simple — M3 doesn't need a full session lifecycle.

- [ ] **Step 2:** Write `data.py`:
```python
"""`sdk.data.*` — the ONLY sanctioned data access path.

Direct pl.read_* / pd.read_* / open() / requests.get() in strategy code is
flagged by `pq check` (M4+). Everything here writes to `lineage_reads`.
"""
from __future__ import annotations
from datetime import date
import io
import polars as pl
import boto3
from quantplatform.sdk.lineage import compute_content_hash, record_read
from quantplatform.sdk.run import current_run_id
from quantplatform.sdk._db import fetch_one
from quantplatform.sdk._config import settings  # S3 endpoint + creds


def ohlcv(*, ticker: str, as_of: date | None = None) -> pl.DataFrame:
    """Load daily OHLCV bars for `ticker`. MVP: only SPY is bundled."""
    if ticker != "SPY":
        raise ValueError(f"only SPY is bundled in MVP; got {ticker!r}")
    run_id = current_run_id()  # raises if outside sdk.run context

    dv = fetch_one(
        "SELECT id, storage_uri FROM dataset_versions dv "
        "JOIN datasets d ON d.id = dv.dataset_id "
        "WHERE d.name = 'ohlcv-spy-daily' AND dv.version_tag = 'v1'"
    )
    if dv is None:
        raise RuntimeError("ohlcv-spy-daily/v1 not registered; is the stack bootstrapped?")

    # Download raw bytes from MinIO
    s3 = boto3.client("s3",
                      endpoint_url=settings.s3_endpoint_url,
                      aws_access_key_id=settings.s3_access_key,
                      aws_secret_access_key=settings.s3_secret_key)
    bucket, key = dv.storage_uri.removeprefix("s3://").split("/", 1)
    raw = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    ch = compute_content_hash(raw)
    df = pl.read_parquet(io.BytesIO(raw))

    # Apply as_of filter if bi-temporal columns exist (MVP: skip — columns don't yet)
    if as_of is not None and "_knowable_at" in df.columns:
        df = df.filter(pl.col("_knowable_at") <= as_of)

    record_read(
        run_id=run_id, dataset_version_id=dv.id, as_of=as_of,
        filter_predicates={"ticker": ticker, "as_of": str(as_of) if as_of else None},
        content_hash=ch, rows_returned=df.height,
    )
    return df
```

- [ ] **Step 3:** Write `__init__.py` for `sdk/`:
```python
"""Quant Platform SDK — strategy-facing API."""
from quantplatform.sdk import data, run
from quantplatform.sdk.strategy import Strategy  # wired in T7

__all__ = ["Strategy", "data", "run"]
```

(Note: the `Strategy` import will fail until T7 lands. Wrap in try/except similar to the M2 validation shim, OR defer adding the Strategy import here until T7. The second option is cleaner — do that.)

Update accordingly: at T4 the `__init__.py` only exports `data` and `run`. T7 adds `Strategy` to the exports.

- [ ] **Step 4:** Write `test_data_ohlcv.py` and `test_lineage.py`. Use testcontainers to spin up postgres + minio; upload the bundled parquet to the test bucket in a fixture; run migrations; call `data.ohlcv(ticker="SPY")` inside a mocked `current_run_id()` context; assert: returned DataFrame matches expected shape (2500-ish rows × 7 cols); `lineage_reads` has one new row with non-null content_hash matching xxhash of the bytes; a `DataRead` event lands in `events`.

Target: 4 unit/integration tests; <15s each.

- [ ] **Step 5:** Run tests and commit as `feat(M3-4): sdk.data.ohlcv with content hashing + lineage writes`.

---

## Task 5: Audit-log hash-chain (port from archive)

**Files:**
- Create: `packages/sdk/src/quantplatform/sdk/audit.py` (port from archive)
- Create: `packages/sdk/tests/sdk/test_audit_log.py` (port from archive)
- Create: `packages/sdk/tests/sdk/test_audit_log_concurrency.py` (port from archive)

The archive's `apps/api/app/audit/log.py` uses `pg_advisory_xact_lock(0xA7D17_106)` to serialize audit-log writes so prev_hash → this_hash forms an unbroken chain even under concurrent writers.

- [ ] **Step 1:** Fetch the archive source:
```bash
(cd ../deployment/quant-platform-archive-2026-04 && \
  git show 'origin/archive/mvp-a-rushed-2026-04-22:apps/api/app/audit/log.py') \
  > packages/sdk/src/quantplatform/sdk/audit.py
```

- [ ] **Step 2:** Review the ported file. Likely adjustments:
- Replace any `app.infra.db` imports with `quantplatform.sdk._db`.
- Remove any reference to `Dagster` / task context (shouldn't be any in audit; confirm).
- Ensure the module exposes `emit_event(run_id, event_type, payload) -> None` that takes care of hash-chain logic internally.

- [ ] **Step 3:** Port the tests:
```bash
(cd ../deployment/quant-platform-archive-2026-04 && \
  git show 'origin/archive/mvp-a-rushed-2026-04-22:apps/api/tests/test_audit_log.py') \
  > packages/sdk/tests/sdk/test_audit_log.py
(cd ../deployment/quant-platform-archive-2026-04 && \
  git show 'origin/archive/mvp-a-rushed-2026-04-22:apps/api/tests/test_audit_log_concurrency.py') \
  > packages/sdk/tests/sdk/test_audit_log_concurrency.py
```
Rewrite `from app.audit.log` imports to `from quantplatform.sdk.audit`.

- [ ] **Step 4:** Run tests (testcontainers-backed; concurrency test uses hypothesis or threading).
```bash
cd packages/sdk && uv run pytest tests/sdk/test_audit_log.py tests/sdk/test_audit_log_concurrency.py -v
```
If the concurrency test fails on CI timing, loosen the example count — don't lower the concurrent-writer count.

- [ ] **Step 5:** Commit as `feat(M3-5): port hash-chained audit log from MVP-A archive`.

---

## Task 6: `sdk.run` — run lifecycle + event emission

**Files:** Create `packages/sdk/src/quantplatform/sdk/run.py` and `packages/sdk/tests/sdk/test_run.py`.

Public contract:
```python
from quantplatform.sdk import run

with run.start(strategy_name="vol-har", as_of="2024-12-01") as r:
    r.log("model trained", model_mlflow_uri=...)
    # inside this block, sdk.data.* is allowed; outside, it raises.
```

Implementation:
- `run.start(...)` opens a DB transaction, inserts a `runs` row (status='running'), sets a `contextvars.ContextVar[str]` `_current_run_id`, emits a `RunStarted` audit event, yields a `Run` dataclass.
- On exit (clean): status='succeeded', emits `RunFinished`. On exception: status='failed', emits `RunFailed` with the exception type; re-raises.
- `current_run_id() -> str` reads the contextvar; raises `RuntimeError` if unset.
- `run.Run` exposes `.id`, `.strategy_name`, `.as_of`, `.log(message, **kwargs)` — `.log` emits a `RunLog` audit event.

- [ ] **Step 1:** Implement the module (~100 lines).
- [ ] **Step 2:** Write tests: start-ok, start-fail-emits-RunFailed, nested-start-forbidden, data-outside-run-raises, contextvar-isolation-between-threads.
- [ ] **Step 3:** Run tests and commit as `feat(M3-6): sdk.run lifecycle with audit-event emission`.

---

## Task 7: `Strategy` base class

**Files:** Create `packages/sdk/src/quantplatform/sdk/strategy.py` and `packages/sdk/tests/sdk/test_strategy.py`.

Public contract (spec §6.1.1):
```python
from quantplatform import Strategy, data

class VolHAR(Strategy):
    name = "vol-har"
    thresholds = {"pbo_max": 0.5, "dsr_min": 0.0}  # advisory only in M3; wired in M4
    def features(self, df): ...
    def model(self): ...
    def target(self, df): ...

strategy = VolHAR()
strategy.train_and_validate(df)
```

`train_and_validate(df)` in M3:
1. Computes features and target from `df`.
2. Walk-forwards over the time index using `quantplatform.validation.walk_forward.fold_dates` with a default config (step=month, train_window=3y, test_window=1m, min_folds=8).
3. For each fold: fit `self.model()` on train, predict test, collect fold metrics.
4. Packs the trained model as an MLflow pyfunc (pipeline = features + model).
5. Logs the pyfunc + fold metrics to MLflow under the current run (uses the MLflow tracking URI from `quantplatform.sdk._config`).
6. Emits `ModelTrained` audit event with the MLflow run ID.
7. **Does NOT invoke PBO/DSR/CPCV math or any gate decision — that's M4.** The fold metrics are persisted for later consumption.

- [ ] **Step 1:** Implement. Keep it small (<200 lines). Use `quantplatform.validation.walk_forward` for fold dates. Use `quantplatform.validation.cpcv` API is NOT called here — walk-forward is the only validation primitive M3 exercises.

- [ ] **Step 2:** Re-export `Strategy` from `quantplatform/sdk/__init__.py` and from `quantplatform/__init__.py`:
```python
# quantplatform/__init__.py
from quantplatform.sdk.strategy import Strategy
from quantplatform.sdk import data, run
__all__ = ["Strategy", "data", "run", "__version__"]
```

- [ ] **Step 3:** Tests: trivial-strategy (features returns df, target returns a constant) should train without raising, log to MLflow (mocked), emit `ModelTrained` event, and produce a `runs` row. Use an in-process MLflow tracking backend (local file store) to avoid cross-container chatter.

- [ ] **Step 4:** Commit as `feat(M3-7): Strategy base class with pyfunc packaging (no gate)`.

---

## Task 8: Jinja templates for hello-world-vol-har

**Files:** Under `packages/sdk/src/quantplatform/templates/hello-world-vol-har/`:
- `src/{{name}}/strategy.py.j2` — the user-authored HAR-style vol-forecast, <40 lines (spec §6.1.1 ergonomic target)
- `src/{{name}}/__init__.py.j2` — empty
- `tests/test_strategy.py.j2` — minimal scaffold
- `pq.toml.j2` — `{name, entry, thresholds, data_deps}`
- `pyproject.toml.j2` — Python project deps (quantplatform, lightgbm)
- `.vscode/launch.json.j2` — "Debug strategy (host)" + "Debug strategy (container)"
- `.vscode/settings.json.j2` — pyright + ruff config
- `.vscode/tasks.json.j2` — pq run, pq e2e tasks
- `.vscode/extensions.json.j2` — recommended: python, ruff, pyright
- `.idea/runConfigurations/Debug_host.xml.j2`
- `.idea/runConfigurations/Debug_container.xml.j2`
- `.devcontainer/devcontainer.json.j2` — optional remote-IDE mode
- `.pre-commit-config.yaml.j2` — ruff + pyright + pq-check-lite (pre-M4 this is a placeholder that exits 0) + unit tests
- `.githooks/pre-push` — `pq e2e`
- `README.md.j2` — quickstart (debug, run, promote)

Render variables: `{name, slug, author, year, ticker=SPY, as_of=today}`.

- [ ] **Step 1:** Write each template. `strategy.py.j2` is the most important — it must compile to ≤40 lines of user code demonstrating: inherit `Strategy`, declare `name` + `thresholds`, implement `features/model/target`, call `data.ohlcv(...)` inside `main()`, call `train_and_validate(df)`.

- [ ] **Step 2:** Include a second template variant `hello-world-returns/` for the M4 "expected to fail the gate" companion. Minimal — differs from vol-HAR only in `target()` (return next-day returns instead of realized variance) and declared thresholds (tighter, to force rejection in M4). Actual gate outcome is M4's concern; M3 just scaffolds it.

- [ ] **Step 3:** No runnable tests for templates alone — T9 exercises them via `pq new`. Commit as `feat(M3-8): hello-world-vol-har + hello-world-returns Jinja templates`.

---

## Task 9: `pq new strategy <name>` CLI command

**Files:**
- Modify: `packages/sdk/src/quantplatform/cli/main.py` (register `new`)
- Create: `packages/sdk/src/quantplatform/cli/new_strategy.py`
- Create: `packages/sdk/tests/test_cli_new_strategy.py`

Contract:
```
pq new strategy <name> [--template returns] [--dir PATH]
```
Writes the scaffolded project to `./<name>/` (or `--dir`) using Jinja. Default template: `hello-world-vol-har`. `--template returns` picks `hello-world-returns`. Refuses if the target directory is non-empty (unless `--force`).

- [ ] **Step 1:** Implement with `jinja2.Environment(loader=PackageLoader('quantplatform', 'templates'))`. Walk the template tree, render each `.j2` file into the target directory (strip the `.j2` suffix), copy non-template files verbatim. Handle `{{name}}` in directory names by substituting after rendering.

- [ ] **Step 2:** Tests: TDD as usual. Scaffold into a `tmp_path`; assert `pq.toml`, `pyproject.toml`, `src/<name>/strategy.py`, `tests/test_strategy.py`, `.vscode/launch.json` exist; assert `strategy.py` parses as valid Python (use `ast.parse`); assert `pq.toml` TOML parses and has the expected fields.

- [ ] **Step 3:** Commit as `feat(M3-9): pq new strategy scaffolds V and R templates`.

---

## Task 10: `pq run <strategy>` CLI command (host mode)

**Files:**
- Modify: `packages/sdk/src/quantplatform/cli/main.py` (register `run`)
- Create: `packages/sdk/src/quantplatform/cli/run.py`
- Create: `packages/sdk/tests/test_cli_run.py`

Contract:
```
pq run <name> [--as-of YYYY-MM-DD] [--debug] [--container]
```

Host-mode flow:
1. Find the project directory (cwd if contains `pq.toml`; or `cwd/<name>` if cwd contains it as a subdir).
2. Read `pq.toml`: `name`, `entry` (e.g. `src.vol_har.strategy:main`), `thresholds`.
3. POST a "strategy upsert" to the API at `http://localhost:18000/strategies` with `{name, entry_point, thresholds, git_sha, uv_lock_hash}` — API returns `strategy_id`.
4. POST a "run create" to `/runs` — API creates the `runs` row inside `sdk.run.start(...)` context.
5. Execute the strategy's `entry_point` as a subprocess (`uv run python -m <entry>`), with environment variables: `QP_RUN_ID`, `QP_STRATEGY_ID`, `DATABASE_URL`, `MLFLOW_TRACKING_URI`, etc.
6. Wait for completion. On exit code 0: call `/runs/<id>/finish`. On non-zero: call `/runs/<id>/fail`.
7. Stream stdout/stderr through to the user. If `--debug`, start a subprocess attached to debugpy on localhost:5678 and wait for debugger before continuing.

**Container mode (`--container`):** defers to T11.

API endpoints referenced above (`/strategies`, `/runs`) are part of this task — add them to `apps/api/src/api/main.py`:
```python
@app.post("/strategies")
def upsert_strategy(body: StrategyUpsert) -> dict[str, str]: ...
@app.post("/runs")
def create_run(body: RunCreate) -> dict[str, str]: ...
@app.post("/runs/{run_id}/finish")
def finish_run(run_id: str) -> dict[str, str]: ...
@app.post("/runs/{run_id}/fail")
def fail_run(run_id: str, body: FailBody) -> dict[str, str]: ...
```

- [ ] **Step 1:** Implement the API endpoints + pydantic models.
- [ ] **Step 2:** Implement `cli/run.py`.
- [ ] **Step 3:** Tests: mock the API calls with `respx` or similar; exercise the happy path and the "strategy subprocess raises" path.
- [ ] **Step 4:** Commit as `feat(M3-10): pq run host mode with strategy upsert + run lifecycle API`.

---

## Task 11: `pq run --container` + debugger attach

**Files:**
- Modify: `packages/sdk/src/quantplatform/cli/run.py` (add `--container` branch)
- Modify: `apps/api/Dockerfile` (add `debugpy` to prod deps; expose :5678 in worker_training role)
- Modify: `docker-compose.yml` — add `worker` service (role=`worker_training`, bind-mount `/workspace`, expose 5678)

Flow for `--container`:
1. Build (or reuse cached) the api image tagged `qp-api:m3`.
2. Bind-mount the user's project at `/workspace` in the worker container.
3. `docker compose run --rm --service-ports -v ./<project>:/workspace worker python -m <entry>`.
4. If `--debug`: set `DEBUGPY_WAIT=1` and print the attach-URL for the user's IDE.

- [ ] **Step 1:** Update Dockerfile + compose.
- [ ] **Step 2:** Extend `run.py`.
- [ ] **Step 3:** Test with a Jinja-rendered hello-world project: `pq new strategy hello --template returns && cd hello && pq run hello --container` end-to-end in an integration test.
- [ ] **Step 4:** Commit as `feat(M3-11): pq run --container with debugpy attach`.

---

## Task 12: `pq e2e` pre-push hook

**Files:**
- Create: `packages/sdk/src/quantplatform/cli/e2e.py`
- Create: `packages/sdk/tests/test_cli_e2e.py`
- Modify: `main.py` to register `e2e`

Contract:
```
pq e2e [--strategy NAME]
```
Runs the full pre-push flow: lint (ruff), type-check (pyright), unit tests (pytest on the project), then `pq run --container <name>` to exercise the strategy inside the worker. Budget <90s with BuildKit + uv cache mounts.

- [ ] **Step 1:** Implement. Mostly orchestration — subprocess calls.
- [ ] **Step 2:** Add the `.githooks/pre-push` template content so scaffolded projects gain it on `pq new`.
- [ ] **Step 3:** Test via integration: build a scaffolded project, run `pq e2e`, assert exit 0, assert timing <90s on cached runs.
- [ ] **Step 4:** Commit as `feat(M3-12): pq e2e pre-push hook`.

---

## Task 13: Install hygiene — `uv tool install` + INSTALL.md

**Files:**
- Create: `docs/INSTALL.md`
- Modify: `README.md` (quickstart section points at INSTALL.md and uses `pq` on PATH)

Content of `docs/INSTALL.md`:
- Prereqs: Python 3.12+, Docker, uv.
- Dev install (clone-based): `git clone ... && uv tool install ./packages/sdk && pq --version`.
- Temporary staging install (pre-M8): `curl -sSfL https://quant.ledgertm.com/install.sh | sh`. The install.sh lives on ubuntu-server behind Caddy per `memory/project_install_endpoints.md`. M3 doesn't set that up — M4/M5 does.
- Target install (M8): `curl -sSfL https://get.pyquant.io/install.sh | sh` (deferred).

- [ ] **Step 1:** Write `docs/INSTALL.md` and update `README.md` quickstart to use `pq` on PATH (drop any remaining `uv run pq` references in docs outside historical HIL records).
- [ ] **Step 2:** Commit as `docs(M3-13): INSTALL.md + README quickstart with pq on PATH`.

---

## Task 14: End-to-end integration test

**Files:** Create `tests/integration/test_pq_run_hello_world.py`.

Full stack: compose up → `pq new strategy hello-m3` → `pq run hello-m3` → verify:
- New `runs` row with `status='succeeded'`
- Non-zero `lineage_reads` rows referencing the spy dataset version
- `events` chain includes `RunStarted`, `DataRead`, `ModelTrained`, `RunFinished` with non-null prev_hash/this_hash forming an unbroken chain
- MLflow has a registered pyfunc model under the run

Use `tmp_path` for the scaffolded project; tear down compose after.

- [ ] **Step 1:** Write the test (inherits the `compose_up` fixture from M1).
- [ ] **Step 2:** Run it. Budget: ~3 minutes on first run (image builds, ~10y of SPY data parquet read, LightGBM fits).
- [ ] **Step 3:** Commit as `test(M3-14): end-to-end pq run hello-world integration test`.

---

## Task 15: M3 HIL checkpoint doc

**Files:** Create `docs/milestones/M3/hil.md`.

Per spec §9 M3 HIL: "Scaffold, run, browse MLflow UI, inspect Postgres lineage, attach debugger, pq doctor." 30 min target.

Structure (using the M1/M2 HIL template):
- Scope of this review (6 bullets: what landed, what didn't)
- Prerequisites (clean clone on `feat/m3-sdk-local-runs`, `uv tool install ./packages/sdk`, docker up)
- Script (target 30 min):
  1. Clone + `uv tool install ./packages/sdk` + `pq --version` shows `pq 0.2.0` (bumped from 0.1.0)
  2. `pq doctor` — 4 OK
  3. `pq up` — full stack healthy (6 services)
  4. `pq new strategy m3-hello` — inspect scaffolded tree
  5. `cd m3-hello && pq run m3-hello` — watch console log of train/walk-forward
  6. Open http://localhost:15000 (MLflow UI) — find the registered pyfunc model
  7. `docker exec pq-postgres psql -U qp -d qp -c "SELECT * FROM lineage_reads ORDER BY id DESC LIMIT 5;"` — verify row shape
  8. `docker exec pq-postgres psql -U qp -d qp -c "SELECT event_type, encode(prev_hash,'hex') as prev, encode(this_hash,'hex') as this FROM events ORDER BY id DESC LIMIT 8;"` — verify chain
  9. Attach a debugger to `pq run m3-hello --debug --container` and hit a breakpoint in `strategy.py`
  10. `pq e2e m3-hello` — container build + run under 90s
- Decision points (4):
  - Is the hello-world strategy template under 40 lines as spec commits? If not, trim.
  - Are the MLflow log keys and event payloads legible?
  - Does the debugger attach flow work cleanly in at least one IDE?
  - Is the 90s `pq e2e` budget actually hit on first vs warm run?
- Sign-off checklist (5)
- Defects found section
- Spec / plan updates triggered section

- [ ] **Step 1:** Write the doc.
- [ ] **Step 2:** Commit as `docs(M3-15): M3 HIL checkpoint script`.

---

## Self-Review

### Spec coverage (§9 M3)

| Spec requirement | Task(s) |
|---|---|
| SDK module with `Strategy`, `sdk.data.ohlcv`, `sdk.run.start` | T4 (data), T6 (run), T7 (strategy) |
| Content-hashed lineage writes | T4 |
| `pq new strategy hello-world` scaffolds V template | T8 (template), T9 (command) |
| `pq run hello-world` executes on host, logs to MLflow, writes runs + events + lineage_reads | T6, T7, T10 |
| NO gate yet | Enforced in T7 (train_and_validate does not call PBO/DSR/CPCV math) |
| Unit: SDK method contracts; lineage record shape; scaffold correctness | T4, T6, T7, T9 |
| Integration: `pq run` against live stack; MLflow run created; lineage rows written; audit log extended | T14 |
| E2E: `pq e2e` container build + run passes in <90s | T12 |
| HIL: scaffold, run, browse MLflow, inspect lineage, attach debugger, pq doctor | T15 |

### Placeholder scan
No TBD / TODO / "similar to". Every task has exact file paths + exact commit messages. Steps that reference archive source give the exact `git show` command. ✓

### Type consistency
- `run_id` is `str` (UUID formatted) in Python; UUID in Postgres.
- `dataset_version_id` same.
- `Strategy.name` is the class-level attribute used in `pq.toml` `name` field and `strategies.name` column — single source of truth.
- `content_hash` is `bytes` (xxh64 digest) everywhere; hex-encoded only at JSON boundaries (events payload).
- `Run` dataclass from `sdk.run` vs `Run` DB row — disambiguated: `run.Run` is the Python dataclass; DB rows are surfaced via fetch helpers as dicts or pydantic models.
- `pq.toml` keys: `name`, `entry`, `thresholds`, `data_deps`. Consistent across T8 template, T9 scaffold, T10 `pq run` reader.

### Scope check
Plan covers one milestone (M3). M4 (gate wiring) gets its own plan post-HIL.

### Open design questions (carried forward)
- **Additional gates extensibility** (`Strategy.additional_gates: list[Gate]`): flagged during M2 HIL as a limitation of hardcoded PBO/DSR/CPCV. Not built in M3 (no gate at all here). Revisit in M4 planning — natural bolt-on when the mandatory gate is wired.

---

## Execution notes

- Task count: 15 tasks, ~70 steps.
- Budget per spec: 4 workdays. Subagent-loop realistic: 40–60 minutes.
- Commit cadence: one commit per task.
- Parallelization: T4 (data), T5 (audit), T6 (run), T7 (strategy), T8 (templates) are mostly independent after T1+T2+T3 land. T9/T10/T11/T12 depend on T7+T8. T14 is last. Despite independence, dispatch serially per the subagent-driven-development skill's rule.
- Risk: MLflow client + LightGBM + polars memory footprint on the first `pq run` may exceed CI's RAM — keep the SPY dataset small (~30 KB parquet → ~2500 rows × 7 cols, trivially fits).
- Risk: `debugpy` / `launch.json` templates are IDE-specific; M3 HIL Step 9 tests one IDE (VS Code primary); PyCharm is scaffolded but un-tested in this HIL. Mark PyCharm as DEFER-TO-V2 if it doesn't work.
