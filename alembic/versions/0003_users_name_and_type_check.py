"""Add users.name and restrict user_type to admin/user.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("name", sa.String(), nullable=False, server_default="")
    )
    op.create_check_constraint(
        "ck_users_user_type",
        "users",
        "user_type IN ('admin', 'user')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_user_type", "users", type_="check")
    op.drop_column("users", "name")
