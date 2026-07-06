from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class OutSchema(BaseModel):
    """Base for response payloads: serializes Python snake_case fields as camelCase
    so the UI's existing `types.ts` interfaces can consume responses as-is."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class LogoutOut(OutSchema):
    detail: str
