from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

ScrapingOutputFormat = Literal["markdown", "json", "xml", "xmltei"]


class OutSchema(BaseModel):
    """Base for response payloads: serializes Python snake_case fields as camelCase so
    the UI's existing `types.ts` interfaces can consume responses as-is."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )


class DataItemOut(OutSchema):
    id: str
    job_id: str
    target_url: str
    url: str
    title: str
    word_count: int
    format: ScrapingOutputFormat
    extracted_at: int
    preview: str


class DataListOut(OutSchema):
    items: list[DataItemOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class DataItemDetailOut(DataItemOut):
    content: dict
