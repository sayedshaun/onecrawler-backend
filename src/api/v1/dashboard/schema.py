from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

CrawlMode = Literal["sitemap", "link_extraction", "crawler"]
CrawlStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class OutSchema(BaseModel):
    """Base for response payloads: serializes Python snake_case fields as camelCase
    so the UI's existing `types.ts` interfaces can consume responses as-is."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class JobCountsOut(OutSchema):
    queued: int
    running: int
    completed: int
    failed: int
    cancelled: int


class RecentJobOut(OutSchema):
    id: str
    target_url: str
    status: CrawlStatus
    mode: CrawlMode
    created_at: int
    urls_discovered: int
    urls_scraped: int


class DashboardOverviewOut(OutSchema):
    total_jobs: int
    job_counts: JobCountsOut
    urls_discovered: int
    urls_scraped: int
    urls_failed: int
    recent_jobs: list[RecentJobOut] = Field(default_factory=list)
