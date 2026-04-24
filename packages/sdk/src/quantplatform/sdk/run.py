"""Run lifecycle: creates the `runs` row, sets a contextvar so sdk.data
can attach lineage to the current run, emits RunStarted / RunFinished /
RunFailed audit events.
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterator

from quantplatform.sdk._db import connection, fetch_one
from quantplatform.sdk.audit import emit_event


_current_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_current_run_id", default=None
)


@dataclass
class Run:
    id: str
    strategy_id: str
    as_of: date | None
    started_at: datetime
    # Filled in on exit
    status: str = "running"
    finished_at: datetime | None = None

    def log(self, message: str, **payload: Any) -> None:
        """Emit a RunLog audit event tied to this run."""
        emit_event(
            run_id=self.id,
            event_type="RunLog",
            payload={"message": message, **payload},
        )


def current_run_id() -> str:
    """Return the ID of the currently-active run, or raise if none."""
    rid = _current_run_id.get()
    if rid is None:
        raise RuntimeError(
            "sdk.data.* called outside of a run.start() context — "
            "lineage cannot be attached. Wrap the call in `with run.start(...):`."
        )
    return rid


@contextmanager
def start(
    *,
    strategy_id: str,
    as_of: date | str | None = None,
    git_sha: str | None = None,
    uv_lock_hash: str | None = None,
) -> Iterator[Run]:
    """Open a run.

    - Inserts a row into `runs` (status=running).
    - Emits `RunStarted` on the audit chain.
    - Sets a contextvar so sdk.data.* can find this run for lineage writes.
    - On clean exit: updates the row to succeeded, emits `RunFinished`.
    - On exception: updates to failed, emits `RunFailed` with the exception info, re-raises.
    - Nested entry raises RuntimeError.
    """
    if _current_run_id.get() is not None:
        raise RuntimeError(
            f"nested run.start() is not allowed; a run is already active "
            f"(id={_current_run_id.get()})"
        )

    # Normalize as_of
    if isinstance(as_of, str):
        as_of_date = date.fromisoformat(as_of)
    else:
        as_of_date = as_of

    # Validate strategy exists and fetch name in one query
    strat = fetch_one(
        "SELECT name FROM strategies WHERE id = %(sid)s",
        sid=strategy_id,
    )
    if strat is None:
        raise ValueError(f"strategy_id {strategy_id!r} not found in strategies table")

    # Insert runs row
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO runs (strategy_id, as_of, status, git_sha, uv_lock_hash)
                VALUES (%(sid)s, %(as_of)s, 'running', %(sha)s, %(lock)s)
                RETURNING id, started_at
                """,
                {"sid": strategy_id, "as_of": as_of_date, "sha": git_sha, "lock": uv_lock_hash},
            )
            row = cur.fetchone()
            run_id = str(row[0])
            started_at = row[1]

    r = Run(id=run_id, strategy_id=strategy_id, as_of=as_of_date, started_at=started_at)

    # Emit RunStarted
    emit_event(
        run_id=run_id,
        event_type="RunStarted",
        payload={
            "strategy_id": strategy_id,
            "strategy_name": strat.name,
            "as_of": as_of_date.isoformat() if as_of_date else None,
            "git_sha": git_sha,
            "uv_lock_hash": uv_lock_hash,
        },
    )

    token = _current_run_id.set(run_id)
    try:
        yield r
    except BaseException as exc:
        # Mark failed
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE runs SET status='failed', finished_at=NOW() WHERE id = %(id)s",
                    {"id": run_id},
                )
        r.status = "failed"
        r.finished_at = datetime.now()
        emit_event(
            run_id=run_id,
            event_type="RunFailed",
            payload={
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
            },
        )
        raise
    else:
        # Mark succeeded
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE runs SET status='succeeded', finished_at=NOW() "
                    "WHERE id = %(id)s",
                    {"id": run_id},
                )
        r.status = "succeeded"
        r.finished_at = datetime.now()
        emit_event(
            run_id=run_id,
            event_type="RunFinished",
            payload={"strategy_id": strategy_id},
        )
    finally:
        _current_run_id.reset(token)
