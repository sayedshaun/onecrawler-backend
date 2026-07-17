from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from src.db.models import CrawlMode, CrawlStatus

LinkExtractionStrategy = Literal["shallow", "deep"]
ScrapingStrategy = Literal["heuristic", "genai", "markdownify"]
ProxyRotationMethod = Literal["round_robin", "random"]
GenAIProvider = Literal["openai", "google", "ollama"]
FilterKind = Literal[
    "by_date", "by_keywords", "by_files", "by_extension", "by_cosine_similarity"
]
FilterGroupMode = Literal["AND", "OR"]


class InSchema(BaseModel):
    """Base for request payloads: accepts the UI's snake_case fields as-is."""

    model_config = ConfigDict(extra="ignore")


class OutSchema(BaseModel):
    """Base for response payloads: serializes Python snake_case fields as camelCase so
    the UI's existing `types.ts` interfaces can consume responses as-is."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )


class ProxySettingsIn(InSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "server": "http://proxy.example.com:8080",
                "username": "proxy-user",
                "password": "proxy-pass",
            }
        }
    )

    server: str
    username: str | None = None
    password: str | None = None


class ViewportIn(InSchema):
    model_config = ConfigDict(
        json_schema_extra={"example": {"width": 1280, "height": 800}}
    )

    width: int
    height: int


class BrowserSettingsIn(InSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "viewport": {"width": 1280, "height": 800},
                "locale": "en-US",
                "timezone_id": "Asia/Dhaka",
                "headless": True,
                "wait_until": "domcontentloaded",
                "timeout": 30000,
            }
        }
    )

    viewport: ViewportIn
    locale: str = "en-US"
    timezone_id: str = "Asia/Dhaka"
    user_agent: str | None = None
    headless: bool = True
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = "domcontentloaded"
    timeout: int = 30000


class HumanBehaviorSettingsIn(InSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "min_delay": 0.3,
                "max_delay": 1.2,
                "max_scrolls": 50,
                "min_mouse_moves": 5,
                "max_mouse_moves": 15,
            }
        }
    )

    min_delay: float = 0.3
    max_delay: float = 1.2
    max_scrolls: int = 50
    min_mouse_moves: int = 5
    max_mouse_moves: int = 15


class GenAISettingsIn(InSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "provider": "openai",
                "model_name": "gpt-4o-mini",
                "api_key": "sk-live-xxxxxxxxxxxxxxxx",
                "base_url": None,
                "timeout": 30.0,
                "output_schema": {"title": "string", "summary": "string"},
            }
        }
    )

    provider: GenAIProvider
    model_name: str
    api_key: str | None = None
    base_url: str | None = None
    timeout: float | None = None
    output_schema: dict[str, str] = Field(default_factory=dict)


class FilterNodeIn(InSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "kind": "by_date",
                "start": "2026-01-01",
                "end": "2026-06-30",
                "keywords": None,
                "types": None,
                "extensions": None,
                "query": None,
                "threshold": None,
            }
        }
    )

    kind: FilterKind
    start: str | None = None
    end: str | None = None
    keywords: list[str] | None = None
    types: list[str] | None = None
    extensions: list[str] | None = None
    query: str | None = None
    threshold: float | None = None

    @field_validator("start", "end")
    @classmethod
    def _validate_date(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("must be a date in YYYY-MM-DD format") from exc
        return value


class FilterGroupIn(InSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mode": "AND",
                "chain": [
                    {
                        "kind": "by_date",
                        "start": "2026-01-01",
                        "end": "2026-06-30",
                    }
                ],
            }
        }
    )

    mode: FilterGroupMode = "AND"
    chain: list[FilterNodeIn] = Field(default_factory=list)


class CrawlSettingsIn(InSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "link_extraction_strategy": "deep",
                "link_extraction_limit": 50,
                "include_link_patterns": None,
                "exclude_link_patterns": None,
                "scraping_strategy": "heuristic",
                "genai": None,
                "concurrency": 10,
                "max_retries": 2,
                "request_timeout": 10,
                "retry_delay": 1,
                "proxies": None,
                "proxy_rotation_method": "round_robin",
                "browser_settings": {
                    "viewport": {"width": 1280, "height": 800},
                    "locale": "en-US",
                    "timezone_id": "Asia/Dhaka",
                    "headless": True,
                    "wait_until": "domcontentloaded",
                    "timeout": 30000,
                },
                "enable_human_behaviors": False,
                "human_behavior_settings": None,
            }
        }
    )

    link_extraction_strategy: LinkExtractionStrategy = "deep"
    link_extraction_limit: int = 50
    include_link_patterns: list[str] | None = Field(
        default=None,
        description="Plain path keywords (e.g. 'sports'), not glob patterns. "
        "The backend expands each into a '/<keyword>/*' pattern for onecrawler.",
    )
    exclude_link_patterns: list[str] | None = Field(
        default=None,
        description="Plain path keywords (e.g. 'sports'), not glob patterns. "
        "The backend expands each into a '/<keyword>/*' pattern for onecrawler.",
    )

    scraping_strategy: ScrapingStrategy = "heuristic"
    genai: GenAISettingsIn | None = None

    concurrency: int = 10
    max_retries: int = 2
    request_timeout: int = 10
    retry_delay: int = 1

    proxies: list[ProxySettingsIn] | None = None
    proxy_rotation_method: ProxyRotationMethod = "round_robin"

    browser_settings: BrowserSettingsIn
    enable_human_behaviors: bool = False
    human_behavior_settings: HumanBehaviorSettingsIn | None = None


class CreateCrawlRequest(InSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "target_url": "https://example.com/blog",
                "mode": "crawler",
                "settings": {
                    "link_extraction_strategy": "deep",
                    "link_extraction_limit": 50,
                    "scraping_strategy": "heuristic",
                    "concurrency": 10,
                    "max_retries": 2,
                    "request_timeout": 10,
                    "retry_delay": 1,
                    "proxy_rotation_method": "round_robin",
                    "browser_settings": {
                        "viewport": {"width": 1280, "height": 800},
                        "locale": "en-US",
                        "timezone_id": "Asia/Dhaka",
                        "headless": True,
                        "wait_until": "domcontentloaded",
                        "timeout": 30000,
                    },
                    "enable_human_behaviors": False,
                },
                "filters": None,
            }
        }
    )

    target_url: str
    mode: CrawlMode
    settings: CrawlSettingsIn
    filters: FilterGroupIn | None = None


class ScrapeFromDiscoveredRequest(InSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "settings": {
                    "link_extraction_strategy": "deep",
                    "link_extraction_limit": 50,
                    "scraping_strategy": "heuristic",
                    "concurrency": 10,
                    "max_retries": 2,
                    "request_timeout": 10,
                    "retry_delay": 1,
                    "proxy_rotation_method": "round_robin",
                    "browser_settings": {
                        "viewport": {"width": 1280, "height": 800},
                        "locale": "en-US",
                        "timezone_id": "Asia/Dhaka",
                        "headless": True,
                        "wait_until": "domcontentloaded",
                        "timeout": 30000,
                    },
                    "enable_human_behaviors": False,
                }
            }
        }
    )

    settings: CrawlSettingsIn


class CrawlJobSummaryOut(OutSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "6f1c9e2a-9b3d-4b1e-9b3d-6f1c9e2a9b3d",
                "targetUrl": "https://example.com/blog",
                "status": "completed",
                "mode": "crawler",
                "createdAt": 1752480000000,
                "startedAt": 1752480005000,
                "finishedAt": 1752480605000,
                "urlsDiscovered": 52,
                "urlsScraped": 50,
                "urlsFailed": 2,
                "urlLimit": 100,
                "error": None,
            }
        }
    )

    id: str
    target_url: str
    status: CrawlStatus
    mode: CrawlMode
    created_at: int
    started_at: int | None = None
    finished_at: int | None = None
    urls_discovered: int
    urls_scraped: int
    urls_failed: int
    url_limit: int
    error: str | None = None


class ThroughputPointOut(OutSchema):
    model_config = ConfigDict(
        json_schema_extra={"example": {"t": 1752480060000, "pagesPerSec": 1.8}}
    )

    t: int
    pages_per_sec: float


class DiscoveryPointOut(OutSchema):
    model_config = ConfigDict(
        json_schema_extra={"example": {"t": 1752480060000, "count": 12}}
    )

    t: int
    count: int


class CrawlJobDetailOut(CrawlJobSummaryOut):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "6f1c9e2a-9b3d-4b1e-9b3d-6f1c9e2a9b3d",
                "targetUrl": "https://example.com/blog",
                "status": "completed",
                "mode": "crawler",
                "createdAt": 1752480000000,
                "startedAt": 1752480005000,
                "finishedAt": 1752480605000,
                "urlsDiscovered": 52,
                "urlsScraped": 50,
                "urlsFailed": 2,
                "urlLimit": 100,
                "error": None,
                "settings": {
                    "link_extraction_strategy": "deep",
                    "scraping_strategy": "heuristic",
                    "concurrency": 10,
                },
                "throughputHistory": [
                    {"t": 1752480060000, "pagesPerSec": 1.8},
                    {"t": 1752480120000, "pagesPerSec": 2.1},
                ],
                "discoveryHistory": [
                    {"t": 1752480060000, "count": 8},
                    {"t": 1752480120000, "count": 20},
                ],
            }
        }
    )

    settings: dict
    throughput_history: list[ThroughputPointOut] = Field(default_factory=list)
    discovery_history: list[DiscoveryPointOut] = Field(default_factory=list)


class CrawlListOut(OutSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "6f1c9e2a-9b3d-4b1e-9b3d-6f1c9e2a9b3d",
                        "targetUrl": "https://example.com/blog",
                        "status": "completed",
                        "mode": "crawler",
                        "createdAt": 1752480000000,
                        "startedAt": 1752480005000,
                        "finishedAt": 1752480605000,
                        "urlsDiscovered": 52,
                        "urlsScraped": 50,
                        "urlsFailed": 2,
                        "urlLimit": 100,
                        "error": None,
                    }
                ],
                "total": 1,
                "limit": 50,
                "offset": 0,
            }
        }
    )

    items: list[CrawlJobSummaryOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class LogLineOut(OutSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "3c2b1a0f-1234-4a5b-8c9d-0e1f2a3b4c5d",
                "timestamp": 1752480060000,
                "level": "info",
                "message": "Extracted https://example.com/blog/post-1",
            }
        }
    )

    id: str
    timestamp: int
    level: Literal["info", "warn", "error", "debug"]
    message: str


class LogListOut(OutSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "3c2b1a0f-1234-4a5b-8c9d-0e1f2a3b4c5d",
                        "timestamp": 1752480060000,
                        "level": "info",
                        "message": "Extracted https://example.com/blog/post-1",
                    }
                ],
                "total": 1,
                "limit": 50,
                "offset": 0,
            }
        }
    )

    items: list[LogLineOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class DiscoveredUrlOut(OutSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "9a8b7c6d-5e4f-4a3b-9c8d-7e6f5a4b3c2d",
                "url": "https://example.com/blog/post-1",
                "discoveredAt": 1752480010000,
                "status": "extracted",
            }
        }
    )

    id: str
    url: str
    discovered_at: int
    status: Literal["pending", "extracted", "filtered", "failed"]


class DiscoveredListOut(OutSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "9a8b7c6d-5e4f-4a3b-9c8d-7e6f5a4b3c2d",
                        "url": "https://example.com/blog/post-1",
                        "discoveredAt": 1752480010000,
                        "status": "extracted",
                    }
                ],
                "total": 1,
                "limit": 50,
                "offset": 0,
            }
        }
    )

    items: list[DiscoveredUrlOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
