import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


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


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    target_url: Mapped[str] = mapped_column(String, nullable=False)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")

    settings: Mapped[dict] = mapped_column(JSONB, nullable=False)
    filters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

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

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False)
    filters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class ProviderApiKey(Base):
    __tablename__ = "provider_api_keys"

    provider: Mapped[str] = mapped_column(String, primary_key=True)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
