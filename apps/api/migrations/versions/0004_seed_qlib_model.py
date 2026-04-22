"""Seed the qlib-lgbm demo model.

Previously seeded inside 0003, but that INSERT was added after 0003 had
already run on live envs, so Alembic skipped it. This standalone migration
ensures the row exists everywhere — and remains idempotent via ON CONFLICT.
"""

from __future__ import annotations

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO models(id, name, description, algorithm, owner_email)
        VALUES (
            'qlib-lgbm',
            'qlib-lgbm',
            'Minimal Alpha-style momentum/vol/volume model, inspired by Microsoft Qlib Alpha158',
            'lightgbm',
            'admin@example.test'
        )
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM models WHERE id = 'qlib-lgbm'")
