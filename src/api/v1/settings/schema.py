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


class CrawlTemplateIn(InSchema):
    name: str
    settings: CrawlSettingsIn
    filters: FilterGroupIn | None = None


class CrawlTemplateOut(OutSchema):
    id: str
    name: str
    settings: dict
    filters: dict | None = None
    created_at: int
    updated_at: int


class CrawlTemplateListOut(OutSchema):
    items: list[CrawlTemplateOut] = Field(default_factory=list)
    total: int


# ---- provider API keys ----


class ApiKeyIn(InSchema):
    api_key: str


class ApiKeyOut(OutSchema):
    provider: GenAIProvider
    has_key: bool
    updated_at: int | None = None
