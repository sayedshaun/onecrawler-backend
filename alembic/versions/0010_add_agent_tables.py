"""Add agent_settings, conversations, chat_messages — the agent's chat and
settings API now lives in the main backend (src/api/v1/agent) instead of a
separate service, so its tables move into the main Alembic history.

A prior standalone deployment of the agent service already created these
three tables itself (via SQLAlchemy create_all against this same shared
Postgres instance, never tracked by Alembic) with a plain-varchar user_id
and no FK to users.id. Where that's the case, this migration ALTERs them
into the FK'd/UUID shape in place (preserving data) instead of trying to
CREATE TABLE over them.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "agent_settings" not in existing_tables:
        op.create_table(
            "agent_settings",
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=False),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("llm_provider", sa.String(), nullable=True),
            sa.Column("llm_model", sa.String(), nullable=True),
            sa.Column("llm_api_key", sa.String(), nullable=True),
            sa.Column("search_provider", sa.String(), nullable=True),
            sa.Column("search_api_key", sa.String(), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
    else:
        op.alter_column(
            "agent_settings",
            "user_id",
            type_=postgresql.UUID(as_uuid=False),
            postgresql_using="user_id::uuid",
        )
        op.create_foreign_key(
            "agent_settings_user_id_fkey",
            "agent_settings",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    if "conversations" not in existing_tables:
        op.create_table(
            "conversations",
            sa.Column("conversation_id", sa.String(), primary_key=True),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=False),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    else:
        op.alter_column(
            "conversations",
            "user_id",
            type_=postgresql.UUID(as_uuid=False),
            postgresql_using="user_id::uuid",
        )
        op.create_foreign_key(
            "conversations_user_id_fkey",
            "conversations",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    if "chat_messages" not in existing_tables:
        op.create_table(
            "chat_messages",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "conversation_id",
                sa.String(),
                sa.ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("role", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_chat_messages_conversation_id", "chat_messages", ["conversation_id"]
        )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_conversation_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_table("agent_settings")
