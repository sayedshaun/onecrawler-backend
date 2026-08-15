from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .pg import Base


class AgentSettings(Base):
    """A OneCrawler user's own agent config, resolved from their verified
    user id (GET /api/users/me) rather than this service's shared .env
    defaults. llm_* is required before /chat works; search_* is independent
    and optional — only needed for the web_search tool."""

    __tablename__ = "agent_settings"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    llm_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String, nullable=True)
    llm_api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    search_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    search_api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Conversation(Base):
    """One row per conversation_id — separate from LangGraph's own
    checkpoint state (which the agent uses for its working memory) so a
    user's chat list can be queried directly instead of parsing checkpoint
    internals. title is set once, from the first message, and left alone on
    later turns."""

    __tablename__ = "conversations"

    conversation_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChatMessage(Base):
    """A single human or ai turn within a conversation, stored purely for
    display in a chat history UI — the agent itself replays state from
    LangGraph's checkpointer, not from this table."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
