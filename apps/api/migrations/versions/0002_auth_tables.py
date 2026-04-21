"""auth: sessions, auth_states, signing_keys

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-21 01:00:00
"""

from __future__ import annotations

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # sessions — BFF browser sessions. Opaque id = the cookie value.
    # Tokens encrypted at rest (AES-256-GCM) via the application layer.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id                   text         PRIMARY KEY,
            user_sub             text         NOT NULL,
            user_email           text         NOT NULL,
            user_name            text,
            roles                text[]       NOT NULL DEFAULT '{}',
            tenant_id            text,
            upstream_idp         text         NOT NULL,
            upstream_sub         text,
            id_token_enc         bytea        NOT NULL,
            access_token_enc     bytea        NOT NULL,
            refresh_token_enc    bytea,
            access_expires_at    timestamptz  NOT NULL,
            refresh_expires_at   timestamptz,
            csrf_token           text         NOT NULL,
            created_at           timestamptz  NOT NULL DEFAULT now(),
            last_seen_at         timestamptz  NOT NULL DEFAULT now(),
            idle_expires_at      timestamptz  NOT NULL,
            absolute_expires_at  timestamptz  NOT NULL,
            ip                   inet,
            user_agent           text,
            revoked_at           timestamptz
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS sessions_idle_expires_idx "
        "ON sessions (idle_expires_at) WHERE revoked_at IS NULL"
    )
    op.execute("CREATE INDEX IF NOT EXISTS sessions_user_sub_idx ON sessions (user_sub)")

    # ------------------------------------------------------------------
    # auth_states — per-redirect OIDC state/nonce/PKCE verifier.
    # Short-lived (5-10 minutes); swept by the scheduler.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_states (
            state          text         PRIMARY KEY,
            nonce          text         NOT NULL,
            code_verifier  text         NOT NULL,
            return_to      text         NOT NULL,
            created_at     timestamptz  NOT NULL DEFAULT now(),
            expires_at     timestamptz  NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS auth_states_expires_idx ON auth_states (expires_at)")

    # ------------------------------------------------------------------
    # signing_keys — metadata for IdP JWT signing keys. The private key
    # lives in Secret Manager (prod) or is generated in-process (dev);
    # this table tracks which keys are currently publishable on /jwks.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS signing_keys (
            kid              text         PRIMARY KEY,
            algorithm        text         NOT NULL,
            public_jwk       jsonb        NOT NULL,
            status           text         NOT NULL
                CHECK (status IN ('active', 'retiring', 'retired')),
            created_at       timestamptz  NOT NULL DEFAULT now(),
            activated_at     timestamptz,
            retire_after     timestamptz
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS signing_keys_status_idx ON signing_keys (status)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS signing_keys")
    op.execute("DROP TABLE IF EXISTS auth_states")
    op.execute("DROP TABLE IF EXISTS sessions")
