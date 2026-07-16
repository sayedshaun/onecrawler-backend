from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from src.api.v1.crawler.schema import CrawlSettingsIn, FilterGroupIn, GenAIProvider


class InSchema(BaseModel):
    """Base for request payloads: accepts the UI's snake_case fields as-is."""

    model_config = ConfigDict(extra="ignore")


class OutSchema(BaseModel):
    """Base for response payloads: serializes Python snake_case fields as camelCase so
    the UI's existing `types.ts` interfaces can consume responses as-is."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )


# ---- crawl settings templates ----


_TEMPLATE_SETTINGS_EXAMPLE = {
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


class CrawlTemplateIn(InSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Daily blog crawl",
                "settings": _TEMPLATE_SETTINGS_EXAMPLE,
                "filters": None,
            }
        }
    )

    name: str
    settings: CrawlSettingsIn
    filters: FilterGroupIn | None = None


class CrawlTemplateOut(OutSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "6f1c9e2a-9b3d-4b1e-9b3d-6f1c9e2a9b3d",
                "name": "Daily blog crawl",
                "settings": _TEMPLATE_SETTINGS_EXAMPLE,
                "filters": None,
                "createdAt": 1752480000000,
                "updatedAt": 1752480000000,
            }
        }
    )

    id: str
    name: str
    settings: dict
    filters: dict | None = None
    created_at: int
    updated_at: int


class CrawlTemplateListOut(OutSchema):
    model_config = ConfigDict(json_schema_extra={"example": {"items": [], "total": 0}})

    items: list[CrawlTemplateOut] = Field(default_factory=list)
    total: int


# ---- provider API keys ----


class ApiKeyIn(InSchema):
    model_config = ConfigDict(
        json_schema_extra={"example": {"api_key": "sk-live-xxxxxxxxxxxxxxxx"}}
    )

    api_key: str


class ApiKeyOut(OutSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "provider": "openai",
                "hasKey": True,
                "updatedAt": 1752480000000,
            }
        }
    )

    provider: GenAIProvider
    has_key: bool
    updated_at: int | None = None
