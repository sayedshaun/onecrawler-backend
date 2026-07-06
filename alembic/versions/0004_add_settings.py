"""add crawl_settings_templates and provider_api_keys tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crawl_settings_templates",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("settings", postgresql.JSONB(), nullable=False),
        sa.Column("filters", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
    )

    op.create_table(
        "provider_api_keys",
        sa.Column("provider", sa.String(), primary_key=True),
        sa.Column("api_key", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("provider_api_keys")
    op.drop_table("crawl_settings_templates")
