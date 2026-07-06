"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crawl_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("target_url", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("settings", postgresql.JSONB(), nullable=False),
        sa.Column("filters", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("started_at", sa.BigInteger(), nullable=True),
        sa.Column("finished_at", sa.BigInteger(), nullable=True),
        sa.Column("urls_discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("urls_scraped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("urls_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("url_limit", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "discovered_urls",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("discovered_at", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
    )
    op.create_index("ix_discovered_urls_job_id", "discovered_urls", ["job_id"])

    op.create_table(
        "crawl_result_items",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False, server_default=""),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("format", sa.String(), nullable=False),
        sa.Column("extracted_at", sa.BigInteger(), nullable=False),
        sa.Column("preview", sa.Text(), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_crawl_result_items_job_id", "crawl_result_items", ["job_id"])

    op.create_table(
        "log_lines",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.BigInteger(), nullable=False),
        sa.Column("level", sa.String(), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=False),
    )
    op.create_index("ix_log_lines_job_id", "log_lines", ["job_id"])


def downgrade() -> None:
    op.drop_table("log_lines")
    op.drop_table("crawl_result_items")
    op.drop_table("discovered_urls")
    op.drop_table("crawl_jobs")
