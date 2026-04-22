"""Append-only, hash-chained audit log.

The audit_log table (migration 0005) is the system of record for
security- and compliance-relevant events: strategy registrations,
model promotions, training-data extractions, inference requests,
administrative configuration changes.

Each row carries the SHA-256 hash of the prior row's `row_hash`
(or NULL for the genesis row) in `prev_hash`, and its own SHA-256
hash of (prev_hash || canonical_payload) in `row_hash`. A verifier
walks the chain from genesis and reports the first break, if any.

The table is append-only at the row level: UPDATE and DELETE raise
'audit_log is append-only' via a BEFORE trigger. TRUNCATE bypasses
the trigger and is reserved for test fixtures only.
"""

from app.audit.log import append_audit_event, verify_audit_chain, AuditChainCheck

__all__ = ["append_audit_event", "verify_audit_chain", "AuditChainCheck"]
