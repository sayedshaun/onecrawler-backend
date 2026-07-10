"""Add seed_urls to crawl_jobs for scraper-mode jobs seeded from discovered URLs.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "crawl_jobs",
        sa.Column("seed_urls", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("crawl_jobs", "seed_urls")
