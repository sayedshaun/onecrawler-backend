"""Convert crawl_result_items.content from text to jsonb.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TO_JSONB_FN = "_crawl_result_content_to_jsonb"


def upgrade() -> None:
    # Existing rows may hold either JSON-encoded text (heuristic dict output) or
    # plain text (e.g. markdown) — wrap whatever doesn't parse as JSON so every
    # row ends up a valid jsonb object.
    op.execute(f"""
        CREATE FUNCTION {_TO_JSONB_FN}(value text) RETURNS jsonb AS $$
        BEGIN
            RETURN value::jsonb;
        EXCEPTION WHEN others THEN
            RETURN jsonb_build_object('text', value);
        END;
        $$ LANGUAGE plpgsql IMMUTABLE;
    """)

    # The old text default ('') can't auto-cast to jsonb, so it must be dropped
    # before changing the column type.
    op.execute("ALTER TABLE crawl_result_items ALTER COLUMN content DROP DEFAULT")
    op.alter_column(
        "crawl_result_items",
        "content",
        type_=postgresql.JSONB(),
        postgresql_using=f"{_TO_JSONB_FN}(content)",
    )
    op.execute(
        "ALTER TABLE crawl_result_items ALTER COLUMN content SET DEFAULT '{}'::jsonb"
    )

    op.execute(f"DROP FUNCTION {_TO_JSONB_FN}(text)")


def downgrade() -> None:
    op.execute("ALTER TABLE crawl_result_items ALTER COLUMN content DROP DEFAULT")
    op.alter_column(
        "crawl_result_items",
        "content",
        type_=sa.Text(),
        postgresql_using="content::text",
    )
    op.execute("ALTER TABLE crawl_result_items ALTER COLUMN content SET DEFAULT ''")
