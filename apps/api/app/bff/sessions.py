"""Postgres-backed BFF sessions. Tokens encrypted at rest."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.infra.crypto import open_, seal


@dataclass
class SessionRecord:
    id: str
    user_sub: str
    user_email: str
    user_name: str | None
    roles: list[str]
    tenant_id: str | None
    upstream_idp: str
    upstream_sub: str | None
    access_token: str
    refresh_token: str | None
    id_token: str
    access_expires_at: datetime
    csrf_token: str
    idle_expires_at: datetime
    absolute_expires_at: datetime


def _new_session_id() -> str:
    return secrets.token_urlsafe(32)


def _new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


async def create_session(
    session: AsyncSession,
    *,
    user_sub: str,
    user_email: str,
    user_name: str | None,
    roles: list[str],
    tenant_id: str | None,
    upstream_idp: str,
    upstream_sub: str | None,
    id_token: str,
    access_token: str,
    refresh_token: str | None,
    access_expires_at: datetime,
    refresh_expires_at: datetime | None,
    ip: str | None,
    user_agent: str | None,
) -> SessionRecord:
    settings = get_settings()
    sid = _new_session_id()
    csrf = _new_csrf_token()
    now = datetime.now(UTC)
    idle_exp = now + timedelta(seconds=settings.bff_session_idle_seconds)
    abs_exp = now + timedelta(seconds=settings.bff_session_absolute_seconds)

    associated = sid.encode()
    id_enc = seal(id_token, associated=associated)
    access_enc = seal(access_token, associated=associated)
    refresh_enc = seal(refresh_token, associated=associated) if refresh_token else None

    await session.execute(
        text(
            """
            INSERT INTO sessions (
              id, user_sub, user_email, user_name, roles, tenant_id,
              upstream_idp, upstream_sub,
              id_token_enc, access_token_enc, refresh_token_enc,
              access_expires_at, refresh_expires_at,
              csrf_token, idle_expires_at, absolute_expires_at,
              ip, user_agent
            ) VALUES (
              :id, :sub, :email, :name, :roles, :tenant,
              :idp, :usub,
              :id_enc, :acc_enc, :ref_enc,
              :acc_exp, :ref_exp,
              :csrf, :idle_exp, :abs_exp,
              :ip, :ua
            )
            """
        ),
        {
            "id": sid,
            "sub": user_sub,
            "email": user_email,
            "name": user_name,
            "roles": roles,
            "tenant": tenant_id,
            "idp": upstream_idp,
            "usub": upstream_sub,
            "id_enc": id_enc,
            "acc_enc": access_enc,
            "ref_enc": refresh_enc,
            "acc_exp": access_expires_at,
            "ref_exp": refresh_expires_at,
            "csrf": csrf,
            "idle_exp": idle_exp,
            "abs_exp": abs_exp,
            "ip": ip,
            "ua": user_agent,
        },
    )
    return SessionRecord(
        id=sid,
        user_sub=user_sub,
        user_email=user_email,
        user_name=user_name,
        roles=roles,
        tenant_id=tenant_id,
        upstream_idp=upstream_idp,
        upstream_sub=upstream_sub,
        access_token=access_token,
        refresh_token=refresh_token,
        id_token=id_token,
        access_expires_at=access_expires_at,
        csrf_token=csrf,
        idle_expires_at=idle_exp,
        absolute_expires_at=abs_exp,
    )


async def load_session(session: AsyncSession, sid: str) -> SessionRecord | None:
    row = await session.execute(
        text(
            """
            SELECT id, user_sub, user_email, user_name, roles, tenant_id,
                   upstream_idp, upstream_sub,
                   id_token_enc, access_token_enc, refresh_token_enc,
                   access_expires_at, csrf_token,
                   idle_expires_at, absolute_expires_at, revoked_at
            FROM sessions WHERE id = :id
            """
        ),
        {"id": sid},
    )
    r = row.first()
    if r is None:
        return None
    (
        id_,
        user_sub,
        email,
        name,
        roles,
        tenant,
        idp,
        usub,
        id_enc,
        acc_enc,
        ref_enc,
        acc_exp,
        csrf,
        idle_exp,
        abs_exp,
        revoked_at,
    ) = r
    now = datetime.now(UTC)
    if revoked_at is not None or idle_exp < now or abs_exp < now:
        return None
    associated = id_.encode()
    return SessionRecord(
        id=id_,
        user_sub=user_sub,
        user_email=email,
        user_name=name,
        roles=list(roles or []),
        tenant_id=tenant,
        upstream_idp=idp,
        upstream_sub=usub,
        access_token=open_(bytes(acc_enc), associated=associated),
        refresh_token=open_(bytes(ref_enc), associated=associated) if ref_enc else None,
        id_token=open_(bytes(id_enc), associated=associated),
        access_expires_at=acc_exp,
        csrf_token=csrf,
        idle_expires_at=idle_exp,
        absolute_expires_at=abs_exp,
    )


async def touch_session(session: AsyncSession, sid: str) -> None:
    """Sliding idle expiry — called on every authenticated request."""
    settings = get_settings()
    await session.execute(
        text(
            "UPDATE sessions SET last_seen_at = now(), "
            "idle_expires_at = now() + make_interval(secs => :idle) "
            "WHERE id = :id AND revoked_at IS NULL"
        ),
        {"id": sid, "idle": settings.bff_session_idle_seconds},
    )


async def revoke_session(session: AsyncSession, sid: str) -> None:
    await session.execute(
        text("UPDATE sessions SET revoked_at = now() WHERE id = :id"), {"id": sid}
    )


async def rotate_session_id(session: AsyncSession, old_sid: str) -> str:
    """Replace session id with a fresh one. Used after login and after refresh."""
    new_sid = _new_session_id()
    # Re-encrypt tokens with new associated data.
    existing = await load_session(session, old_sid)
    if existing is None:
        raise RuntimeError("cannot rotate missing session")
    associated_new = new_sid.encode()
    id_enc = seal(existing.id_token, associated=associated_new)
    acc_enc = seal(existing.access_token, associated=associated_new)
    ref_enc = (
        seal(existing.refresh_token, associated=associated_new) if existing.refresh_token else None
    )

    # Swap id atomically: insert new row, drop old row.
    await session.execute(
        text(
            """
            INSERT INTO sessions (
              id, user_sub, user_email, user_name, roles, tenant_id,
              upstream_idp, upstream_sub,
              id_token_enc, access_token_enc, refresh_token_enc,
              access_expires_at, csrf_token, idle_expires_at, absolute_expires_at
            )
            SELECT :nid, user_sub, user_email, user_name, roles, tenant_id,
                   upstream_idp, upstream_sub,
                   :id_enc, :acc_enc, :ref_enc,
                   access_expires_at, csrf_token,
                   idle_expires_at, absolute_expires_at
            FROM sessions WHERE id = :oid
            """
        ),
        {
            "nid": new_sid,
            "oid": old_sid,
            "id_enc": id_enc,
            "acc_enc": acc_enc,
            "ref_enc": ref_enc,
        },
    )
    await session.execute(text("DELETE FROM sessions WHERE id = :oid"), {"oid": old_sid})
    return new_sid


async def update_tokens(
    session: AsyncSession,
    sid: str,
    *,
    id_token: str,
    access_token: str,
    refresh_token: str,
    access_expires_at: datetime,
    refresh_expires_at: datetime,
) -> None:
    associated = sid.encode()
    await session.execute(
        text(
            """
            UPDATE sessions SET
              id_token_enc      = :id_enc,
              access_token_enc  = :acc_enc,
              refresh_token_enc = :ref_enc,
              access_expires_at = :acc_exp,
              refresh_expires_at = :ref_exp
            WHERE id = :id
            """
        ),
        {
            "id": sid,
            "id_enc": seal(id_token, associated=associated),
            "acc_enc": seal(access_token, associated=associated),
            "ref_enc": seal(refresh_token, associated=associated),
            "acc_exp": access_expires_at,
            "ref_exp": refresh_expires_at,
        },
    )
