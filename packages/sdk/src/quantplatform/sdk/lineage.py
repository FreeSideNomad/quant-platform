"""Lineage writer: every sdk.data.* call lands a row in lineage_reads
and emits a DataRead audit event."""
from __future__ import annotations

import json
from datetime import date
from typing import Any

import xxhash

from quantplatform.sdk._db import connection
from quantplatform.sdk.audit import emit_event


def compute_content_hash(raw_bytes: bytes) -> bytes:
    """xxh64 digest of raw file bytes. Deterministic across platforms."""
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
    """Insert a lineage_reads row and emit the corresponding DataRead event."""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO lineage_reads
                    (run_id, dataset_version_id, as_of, filter_predicates,
                     content_hash, read_timestamp, rows_returned)
                VALUES
                    (%(rid)s, %(dv)s, %(as_of)s, %(preds)s::jsonb,
                     %(ch)s, NOW(), %(rows)s)
                """,
                {
                    "rid": run_id,
                    "dv": dataset_version_id,
                    "as_of": as_of,
                    "preds": json.dumps(filter_predicates),
                    "ch": content_hash,
                    "rows": rows_returned,
                },
            )

    emit_event(
        run_id=run_id,
        event_type="DataRead",
        payload={
            "dataset_version_id": str(dataset_version_id),
            "content_hash": content_hash.hex(),
            "rows_returned": rows_returned,
            "filter_predicates": filter_predicates,
        },
    )
