"""Append-only, hash-chained audit log for the events table.

Ported from apps/api/app/audit/log.py (MVP-A archive).

The events table (defined in the v1 migration) is the system of record for
security- and compliance-relevant events: run lifecycle, data reads,
strategy registrations, etc.

Each row carries the SHA-256 hash of the prior row's ``this_hash``
(or b'' for the genesis row) in ``prev_hash``, and its own SHA-256
hash of ``(prev_hash || canonical_payload)`` in ``this_hash``. A
verifier walks the chain from genesis and reports the first break.

Concurrency: all appenders are serialised through a Postgres
advisory transaction-level lock (key 0xA7D17106 — "audit log"
mnemonic, spec decision #13, LESSONS.md §worth-keeping). Two
concurrent callers queue at the lock; only one holds it at a time;
the lock releases at commit/rollback. This is necessary because READ
COMMITTED snapshots allow concurrent transactions to read the same
"latest row" before either commits, producing duplicate prev_hash
values.

Schema changes from archive vs. the v1 migration:
- Table renamed audit_log → events.
- id is UUID (not serial int) — still returned by RETURNING id.
- actor, aggregate_type, aggregate_id columns removed from events;
  callers encode that information in payload if needed.
- prev_hash / this_hash are BYTEA (raw bytes) rather than TEXT
  hex strings. Genesis row uses b'' to satisfy NOT NULL constraint.
- run_id UUID NULL foreign key to runs(id) — callers pass str | None.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from quantplatform.sdk._db import connection

# Stable integer namespace for the advisory lock — released at commit/rollback.
_AUDIT_LOG_LOCK_KEY = 0xA7D17_106  # "audit log" mnemonic


def _canonical_payload(payload: dict[str, Any]) -> bytes:
    """JSON-serialise payload deterministically for hashing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _compute_this_hash(prev_hash_bytes: bytes, canonical_payload: bytes) -> bytes:
    """SHA-256(prev_hash_bytes || b':' || canonical_payload) → raw bytes."""
    h = hashlib.sha256()
    h.update(prev_hash_bytes)
    h.update(b":")
    h.update(canonical_payload)
    return h.digest()


def emit_event(
    *,
    run_id: str | None,
    event_type: str,
    payload: dict[str, Any],
) -> str:
    """Append an event to the hash-chained events table.

    Acquires the advisory lock, reads the chain tail, computes
    prev_hash and this_hash, inserts the new row, and commits.

    Returns the new row's id (UUID string).
    """
    with connection() as conn:
        with conn.cursor() as cur:
            # Serialise all appenders through the advisory lock.
            cur.execute(
                "SELECT pg_advisory_xact_lock(%(key)s)",
                {"key": _AUDIT_LOG_LOCK_KEY},
            )

            # Safe to read chain tail — we hold the exclusive lock.
            # We cannot use ORDER BY created_at / id because created_at has
            # millisecond resolution (two rows inserted in the same tick are
            # unordered) and UUID id has no natural sequence correlation.
            # Instead, find the tail by chain linkage: the row whose this_hash
            # is not referenced as any other row's prev_hash. Under the
            # advisory lock, at most one such row exists at a time.
            cur.execute(
                """
                SELECT this_hash FROM events
                WHERE this_hash NOT IN (
                    SELECT prev_hash FROM events
                    WHERE prev_hash != %(genesis)s
                )
                LIMIT 1
                """,
                {"genesis": memoryview(b"")},
            )
            row = cur.fetchone()
            # Genesis: prev_hash is b'' (satisfies NOT NULL); subsequent rows
            # chain to the previous this_hash bytes.
            prev_hash_bytes: bytes = row[0].tobytes() if row else b""

            canonical = _canonical_payload(payload)
            new_this_hash = _compute_this_hash(prev_hash_bytes, canonical)

            # run_id: keep as UUID string or None
            run_id_val = str(run_id) if run_id else None

            cur.execute(
                """
                INSERT INTO events
                    (run_id, event_type, payload, prev_hash, this_hash)
                VALUES
                    (%(run_id)s, %(event_type)s, %(payload)s::jsonb,
                     %(prev_hash)s, %(this_hash)s)
                RETURNING id
                """,
                {
                    "run_id": run_id_val,
                    "event_type": event_type,
                    "payload": canonical.decode("utf-8"),
                    "prev_hash": psycopg2_bytes(prev_hash_bytes),
                    "this_hash": psycopg2_bytes(new_this_hash),
                },
            )
            new_id = cur.fetchone()[0]
        # connection() commits on clean exit
    return str(new_id)


# psycopg2 needs memoryview or bytes for BYTEA columns.
def psycopg2_bytes(b: bytes) -> memoryview:
    return memoryview(b)


# Sync alias — SDK callers are synchronous strategy code.
emit_event_sync = emit_event


@dataclass
class ChainCheck:
    ok: bool
    checked: int
    first_break: str | None  # UUID of the first row whose hash does not match
    detail: str | None


def verify_chain() -> ChainCheck:
    """Walk the events table from genesis and verify each this_hash.

    Returns a ChainCheck with ok=True if the chain is intact.

    We traverse by following the prev_hash → this_hash linkage rather
    than relying on created_at ordering, which can be identical for
    concurrent inserts arriving within the same clock tick. The
    advisory lock guarantees that every row has a unique prev_hash;
    we exploit that to reconstruct the traversal order exactly.

    Note: this materialises the full chain into memory. For MVP-B this
    is acceptable; add streaming (server-side cursor) once events
    exceeds ~1M rows.
    """
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, payload::text AS payload, prev_hash, this_hash FROM events"
            )
            rows = cur.fetchall()

    if not rows:
        return ChainCheck(ok=True, checked=0, first_break=None, detail=None)

    # Build a lookup from prev_hash_bytes → row tuple for chain traversal.
    by_prev: dict[bytes, tuple] = {}
    for row in rows:
        row_id, payload_text, prev_hash_mem, this_hash_mem = row
        prev_bytes = prev_hash_mem.tobytes() if prev_hash_mem is not None else b""
        by_prev[prev_bytes] = row

    # Genesis row is the one with prev_hash = b''.
    if b"" not in by_prev:
        return ChainCheck(
            ok=False,
            checked=0,
            first_break=None,
            detail="genesis row (prev_hash=b'') not found",
        )

    checked = 0
    expected_prev_bytes: bytes = b""
    while True:
        if expected_prev_bytes not in by_prev:
            break  # chain complete
        row_id, payload_text, prev_hash_mem, this_hash_mem = by_prev[expected_prev_bytes]
        row_id_str = str(row_id)
        stored_prev = prev_hash_mem.tobytes() if prev_hash_mem is not None else b""
        stored_this = this_hash_mem.tobytes() if this_hash_mem is not None else b""

        # Validate stored prev matches our traversal cursor.
        if stored_prev != expected_prev_bytes:
            return ChainCheck(
                ok=False,
                checked=checked,
                first_break=row_id_str,
                detail=f"prev_hash mismatch at id={row_id_str}",
            )

        canonical = json.dumps(
            json.loads(payload_text), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        recomputed = _compute_this_hash(expected_prev_bytes, canonical)
        if recomputed != stored_this:
            return ChainCheck(
                ok=False,
                checked=checked,
                first_break=row_id_str,
                detail=f"this_hash mismatch at id={row_id_str}",
            )
        checked += 1
        expected_prev_bytes = stored_this

    if checked != len(rows):
        return ChainCheck(
            ok=False,
            checked=checked,
            first_break=None,
            detail=f"traversal visited {checked} rows but table has {len(rows)}; possible fork in chain",
        )

    return ChainCheck(ok=True, checked=checked, first_break=None, detail=None)
