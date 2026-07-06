from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
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
    """Base for response payloads: serializes Python snake_case fields as camelCase
    so the UI's existing `types.ts` interfaces can consume responses as-is."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )


class ProxySettingsIn(InSchema):
    server: str
    username: Optional[str] = None
    password: Optional[str] = None


class ViewportIn(InSchema):
    width: int
    height: int


class BrowserSettingsIn(InSchema):
    viewport: ViewportIn
    locale: str = "en-US"
    timezone_id: str = "Asia/Dhaka"
    user_agent: Optional[str] = None
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
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: Optional[float] = None
    output_schema: dict[str, str] = Field(default_factory=dict)


class FilterNodeIn(InSchema):
    kind: FilterKind
    start: Optional[str] = None
    end: Optional[str] = None
    keywords: Optional[list[str]] = None
    types: Optional[list[str]] = None
    extensions: Optional[list[str]] = None
    query: Optional[str] = None
    threshold: Optional[float] = None


class FilterGroupIn(InSchema):
    mode: FilterGroupMode = "AND"
    chain: list[FilterNodeIn] = Field(default_factory=list)


class CrawlSettingsIn(InSchema):
    link_extraction_strategy: LinkExtractionStrategy = "deep"
    link_extraction_limit: int = 50
    include_link_patterns: Optional[list[str]] = None
    exclude_link_patterns: Optional[list[str]] = None

    scraping_strategy: ScrapingStrategy = "heuristic"
    scraping_output_format: ScrapingOutputFormat = "json"
    genai: Optional[GenAISettingsIn] = None

    concurrency: int = 10
    max_retries: int = 2
    request_timeout: int = 10
    retry_delay: int = 1

    proxies: Optional[list[ProxySettingsIn]] = None
    proxy_rotation_method: ProxyRotationMethod = "round_robin"

    browser_settings: BrowserSettingsIn
    enable_human_behaviors: bool = False
    human_behavior_settings: Optional[HumanBehaviorSettingsIn] = None


class CreateCrawlRequest(InSchema):
    target_url: str
    mode: CrawlMode
    settings: CrawlSettingsIn
    filters: Optional[FilterGroupIn] = None


class CrawlJobSummaryOut(OutSchema):
    id: str
    target_url: str
    status: CrawlStatus
    mode: CrawlMode
    created_at: int
    started_at: Optional[int] = None
    finished_at: Optional[int] = None
    urls_discovered: int
    urls_scraped: int
    urls_failed: int
    url_limit: int
    error: Optional[str] = None


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
