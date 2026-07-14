"""Add refresh_sessions so issued refresh tokens can be listed and revoked individually
(needed for a "view/revoke active sessions" API).

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "refresh_sessions",
        sa.Column("jti", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("revoked_at", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_sessions_user_id", table_name="refresh_sessions")
    op.drop_table("refresh_sessions")
