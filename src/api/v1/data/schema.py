from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from src.db.models import ScrapingOutputFormat


class InSchema(BaseModel):
    """Base for request payloads: accepts the UI's snake_case fields as-is."""

    model_config = ConfigDict(extra="ignore")


class OutSchema(BaseModel):
    """Base for response payloads: serializes Python snake_case fields as camelCase so
    the UI's existing `types.ts` interfaces can consume responses as-is."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )


class ExportArchiveFormat(str, Enum):
    zip = "zip"
    ndjson = "ndjson"


class DataExportRequest(InSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ids": [
                        "9a8b7c6d-5e4f-4a3b-9c8d-7e6f5a4b3c2d",
                        "3c2b1a0f-1234-4a5b-8c9d-0e1f2a3b4c5d",
                    ],
                    "archive_format": "zip",
                },
                {
                    "job_id": "6f1c9e2a-9b3d-4b1e-9b3d-6f1c9e2a9b3d",
                    "format": "markdown",
                    "q": "pricing",
                    "archive_format": "ndjson",
                },
            ]
        }
    )

    # Selection mode A: explicit rows the user checked in the UI.
    ids: list[str] | None = Field(default=None, max_length=500)

    # Selection mode B: same filters as GET /api/v1/data — export every
    # matching row, not just the current page.
    job_id: str | None = None
    format: str | None = None
    q: str | None = None

    archive_format: ExportArchiveFormat = ExportArchiveFormat.zip

    @model_validator(mode="after")
    def one_selection_mode(self):
        has_ids = bool(self.ids)
        has_filters = any([self.job_id, self.format, self.q])
        if has_ids and has_filters:
            raise ValueError("Pass either ids or filters, not both.")
        if not has_ids and not has_filters:
            raise ValueError("Pass ids or at least one filter (job_id/format/q).")
        return self


class DataItemOut(OutSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "9a8b7c6d-5e4f-4a3b-9c8d-7e6f5a4b3c2d",
                "jobId": "6f1c9e2a-9b3d-4b1e-9b3d-6f1c9e2a9b3d",
                "targetUrl": "https://example.com/blog",
                "url": "https://example.com/blog/post-1",
                "title": "Our 2026 Pricing Update",
                "wordCount": 842,
                "format": "markdown",
                "extractedAt": 1752480060000,
                "preview": "We're updating our pricing tiers starting next quarter...",
            }
        }
    )

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
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "9a8b7c6d-5e4f-4a3b-9c8d-7e6f5a4b3c2d",
                        "jobId": "6f1c9e2a-9b3d-4b1e-9b3d-6f1c9e2a9b3d",
                        "targetUrl": "https://example.com/blog",
                        "url": "https://example.com/blog/post-1",
                        "title": "Our 2026 Pricing Update",
                        "wordCount": 842,
                        "format": "markdown",
                        "extractedAt": 1752480060000,
                        "preview": "We're updating our pricing tiers next quarter...",
                    }
                ],
                "total": 1,
                "limit": 50,
                "offset": 0,
            }
        }
    )

    items: list[DataItemOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class DataItemDetailOut(DataItemOut):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "9a8b7c6d-5e4f-4a3b-9c8d-7e6f5a4b3c2d",
                "jobId": "6f1c9e2a-9b3d-4b1e-9b3d-6f1c9e2a9b3d",
                "targetUrl": "https://example.com/blog",
                "url": "https://example.com/blog/post-1",
                "title": "Our 2026 Pricing Update",
                "wordCount": 842,
                "format": "markdown",
                "extractedAt": 1752480060000,
                "preview": "We're updating our pricing tiers starting next quarter...",
                "content": {
                    "markdown": "# Our 2026 Pricing Update\n\nWe're updating tiers..."
                },
            }
        }
    )

    content: dict
