import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class CrawlStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CrawlMode(StrEnum):
    SITEMAP = "sitemap"
    LINK_EXTRACTION = "link_extraction"
    CRAWLER = "crawler"
    SCRAPER = "scraper"


class ScrapingOutputFormat(StrEnum):
    MARKDOWN = "markdown"
    JSON = "json"
    XML = "xml"
    XMLTEI = "xmltei"


class Users(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    name: Mapped[str] = mapped_column(String, nullable=False, default="")
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    user_type: Mapped[str] = mapped_column(String, nullable=False, default="user")


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    jti: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    revoked_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_url: Mapped[str] = mapped_column(String, nullable=False)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=CrawlStatus.QUEUED
    )

    settings: Mapped[dict] = mapped_column(JSONB, nullable=False)
    filters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    seed_urls: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    started_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    finished_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    urls_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    urls_scraped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    urls_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    url_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    discovered: Mapped[list["DiscoveredUrl"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="DiscoveredUrl.discovered_at",
    )
    results: Mapped[list["CrawlResultItem"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="CrawlResultItem.extracted_at",
    )
    logs: Mapped[list["LogLine"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="LogLine.timestamp"
    )


class DiscoveredUrl(Base):
    __tablename__ = "discovered_urls"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    job_id: Mapped[str] = mapped_column(ForeignKey("crawl_jobs.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(String, nullable=False)
    discovered_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")

    job: Mapped["CrawlJob"] = relationship(back_populates="discovered")


class CrawlResultItem(Base):
    __tablename__ = "crawl_result_items"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    job_id: Mapped[str] = mapped_column(ForeignKey("crawl_jobs.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False, default="")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    format: Mapped[str] = mapped_column(String, nullable=False)
    extracted_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    preview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    job: Mapped["CrawlJob"] = relationship(back_populates="results")


class LogLine(Base):
    __tablename__ = "log_lines"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    job_id: Mapped[str] = mapped_column(ForeignKey("crawl_jobs.id", ondelete="CASCADE"))
    timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False)
    level: Mapped[str] = mapped_column(String, nullable=False, default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)

    job: Mapped["CrawlJob"] = relationship(back_populates="logs")


class CrawlSettingsTemplate(Base):
    __tablename__ = "crawl_settings_templates"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "name", name="uq_crawl_settings_templates_user_id_name"
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False)
    filters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class ProviderApiKey(Base):
    __tablename__ = "provider_api_keys"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    provider: Mapped[str] = mapped_column(String, primary_key=True)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class AgentSettings(Base):
    """A user's own agent config.

    llm_* is required before /chat works; search_* is independent and optional — only
    needed for the web_search tool. llm_base_url is set only for the
    openai_compatible provider (a self-hosted llama.cpp/vLLM-style server).
    """

    __tablename__ = "agent_settings"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    llm_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String, nullable=True)
    llm_api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    llm_base_url: Mapped[str | None] = mapped_column(String, nullable=True)
    search_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    search_api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Conversation(Base):
    """One row per conversation_id — separate from LangGraph's own checkpoint state
    (which the agent uses for its working memory) so a user's chat list can be queried
    directly instead of parsing checkpoint internals.

    title is set once, from the first message, and left alone on later turns.
    """

    __tablename__ = "conversations"

    conversation_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChatMessage(Base):
    """A single human or ai turn within a conversation, stored purely for display in a
    chat history UI — the agent itself replays state from LangGraph's checkpointer, not
    from this table."""

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
