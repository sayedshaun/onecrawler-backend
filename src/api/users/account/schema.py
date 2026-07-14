from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic.alias_generators import to_camel

from src.api.v1.dashboard.schema import JobCountsOut


class InSchema(BaseModel):
    """Base for request payloads: accepts the UI's snake_case fields as-is."""

    model_config = ConfigDict(extra="ignore")


class OutSchema(BaseModel):
    """Base for response payloads: serializes Python snake_case fields as camelCase so
    the UI's existing `types.ts` interfaces can consume responses as-is."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )


class RenameRequest(InSchema):
    name: str = Field(min_length=1)


class ChangeEmailRequest(InSchema):
    email: EmailStr
    password: str


class ChangePasswordRequest(InSchema):
    current_password: str
    new_password: str = Field(min_length=8)


class ChangePasswordOut(OutSchema):
    detail: str


class UsageOut(OutSchema):
    total_jobs: int
    job_counts: JobCountsOut
    urls_discovered: int
    urls_scraped: int
    urls_failed: int
    jobs_this_month: int
    urls_scraped_this_month: int
