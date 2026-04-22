"""Append + verify primitives for the hash-chained audit_log table."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _canonical_payload(payload: dict[str, Any]) -> bytes:
    """JSON-serialise payload deterministically for hashing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _row_hash(prev_hash: str | None, canonical_payload: bytes) -> str:
    """SHA-256(prev_hash || canonical_payload), hex-encoded."""
    h = hashlib.sha256()
    h.update((prev_hash or "").encode("utf-8"))
    h.update(b":")
    h.update(canonical_payload)
    return h.hexdigest()


async def append_audit_event(
    session: AsyncSession,
    *,
    actor: str,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
) -> int:
    """Append an event to audit_log with the correct hash chain.

    Returns the new row's id. Caller is responsible for `session.commit()`.

    Concurrency: this function takes a row-level lock on the latest
    row before computing prev_hash to prevent two concurrent appends
    from chaining to the same prior row. The lock is released on
    commit/rollback.
    """
    latest = (
        await session.execute(
            text(
                """
                SELECT row_hash FROM audit_log
                ORDER BY id DESC LIMIT 1
                FOR UPDATE
                """
            )
        )
    ).scalar_one_or_none()

    canonical = _canonical_payload(payload)
    new_hash = _row_hash(latest, canonical)

    result = await session.execute(
        text(
            """
            INSERT INTO audit_log
                (actor, event_type, aggregate_type, aggregate_id, payload, prev_hash, row_hash)
            VALUES
                (:actor, :event_type, :aggregate_type, :aggregate_id,
                 cast(:payload as jsonb),
                 :prev_hash, :row_hash)
            RETURNING id
            """
        ),
        {
            "actor": actor,
            "event_type": event_type,
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "payload": canonical.decode("utf-8"),
            "prev_hash": latest,
            "row_hash": new_hash,
        },
    )
    return result.scalar_one()


@dataclass
class AuditChainCheck:
    ok: bool
    checked: int
    first_break: int | None  # id of the first row whose hash does not match
    detail: str | None


async def verify_audit_chain(session: AsyncSession) -> AuditChainCheck:
    """Walk the audit_log from genesis and verify each row_hash."""
    rows = (
        await session.execute(
            text(
                """
                SELECT id, payload::text AS payload, prev_hash, row_hash
                FROM audit_log
                ORDER BY id ASC
                """
            )
        )
    ).all()

    expected_prev: str | None = None
    for row in rows:
        if row.prev_hash != expected_prev:
            return AuditChainCheck(
                ok=False,
                checked=row.id,
                first_break=row.id,
                detail=f"prev_hash mismatch at id={row.id}",
            )
        canonical = json.dumps(json.loads(row.payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
        recomputed = _row_hash(expected_prev, canonical)
        if recomputed != row.row_hash:
            return AuditChainCheck(
                ok=False,
                checked=row.id,
                first_break=row.id,
                detail=f"row_hash mismatch at id={row.id}",
            )
        expected_prev = row.row_hash

    return AuditChainCheck(ok=True, checked=len(rows), first_break=None, detail=None)
