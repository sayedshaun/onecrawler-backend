"""Add agent_settings.llm_base_url — the agent can now talk to a self-hosted
OpenAI-compatible server (llama.cpp, vLLM, LM Studio) whose URL, unlike the
hosted providers', has to be configured per user.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_settings", sa.Column("llm_base_url", sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("agent_settings", "llm_base_url")
