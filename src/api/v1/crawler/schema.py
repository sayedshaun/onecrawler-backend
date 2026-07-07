from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

LinkExtractionStrategy = Literal["shallow", "deep"]
ScrapingStrategy = Literal["heuristic", "genai"]
ScrapingOutputFormat = Literal["markdown", "json", "xml", "xmltei"]
ProxyRotationMethod = Literal["round_robin", "random"]
GenAIProvider = Literal["openai", "google", "ollama"]
CrawlMode = Literal["sitemap", "link_extraction", "crawler"]
FilterKind = Literal[
    "by_date", "by_keywords", "by_files", "by_extension", "by_cosine_similarity"
]
FilterGroupMode = Literal["AND", "OR"]
CrawlStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


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
    server: str
    username: str | None = None
    password: str | None = None


class ViewportIn(InSchema):
    width: int
    height: int


class BrowserSettingsIn(InSchema):
    viewport: ViewportIn
    locale: str = "en-US"
    timezone_id: str = "Asia/Dhaka"
    user_agent: str | None = None
    headless: bool = True
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = "domcontentloaded"
    timeout: int = 30000


class HumanBehaviorSettingsIn(InSchema):
    min_delay: float = 0.3
    max_delay: float = 1.2
    max_scrolls: int = 50
    min_mouse_moves: int = 5
    max_mouse_moves: int = 15


class GenAISettingsIn(InSchema):
    provider: GenAIProvider
    model_name: str
    api_key: str | None = None
    base_url: str | None = None
    timeout: float | None = None
    output_schema: dict[str, str] = Field(default_factory=dict)


class FilterNodeIn(InSchema):
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
    mode: FilterGroupMode = "AND"
    chain: list[FilterNodeIn] = Field(default_factory=list)


class CrawlSettingsIn(InSchema):
    link_extraction_strategy: LinkExtractionStrategy = "deep"
    link_extraction_limit: int = 50
    include_link_patterns: list[str] | None = None
    exclude_link_patterns: list[str] | None = None

    scraping_strategy: ScrapingStrategy = "heuristic"
    scraping_output_format: ScrapingOutputFormat = "json"
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
                    "scraping_output_format": "json",
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


class CrawlJobSummaryOut(OutSchema):
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
    t: int
    pages_per_sec: float


class CrawlJobDetailOut(CrawlJobSummaryOut):
    settings: dict
    throughput_history: list[ThroughputPointOut] = Field(default_factory=list)


class CrawlListOut(OutSchema):
    items: list[CrawlJobSummaryOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class LogLineOut(OutSchema):
    id: str
    timestamp: int
    level: Literal["info", "warn", "error", "debug"]
    message: str


class LogListOut(OutSchema):
    items: list[LogLineOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class DiscoveredUrlOut(OutSchema):
    id: str
    url: str
    discovered_at: int
    status: Literal["pending", "extracted", "filtered", "failed"]


class DiscoveredListOut(OutSchema):
    items: list[DiscoveredUrlOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
