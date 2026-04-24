"""Internal DB-connection helper shared by audit, run, data, lineage.

Opens short-lived psycopg2 connections to Postgres using DATABASE_URL.
No connection pooling at M3 — SDK calls are infrequent and per-run
strategies are short-lived subprocesses.

For async needs (M4+ when the API handles high-throughput writes),
migrate to an asyncpg pool at that point.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

import psycopg2
import psycopg2.extras


def _conn_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL is not set; SDK DB access needs it")
    # Alembic/SQLAlchemy use `+psycopg2`; raw psycopg2 wants plain `postgresql://`
    return url.replace("+asyncpg", "").replace("+psycopg2", "")


@contextmanager
def connection() -> Iterator[psycopg2.extensions.connection]:
    """Yield a raw psycopg2 connection with autocommit off.

    Commits on clean exit; rolls back on exception.
    """
    conn = psycopg2.connect(_conn_url())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@dataclass
class Row:
    """Lightweight attribute-accessible view over a psycopg2 dict row."""

    _data: dict[str, Any]

    def __getattr__(self, k: str) -> Any:
        try:
            return self._data[k]
        except KeyError as e:
            raise AttributeError(k) from e


def execute(sql: str, **params: Any) -> None:
    """Execute a statement with named params; no result expected."""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)


def fetch_one(sql: str, **params: Any) -> Row | None:
    with connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return Row(dict(row)) if row else None


def fetch_all(sql: str, **params: Any) -> list[Row]:
    with connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [Row(dict(r)) for r in cur.fetchall()]
