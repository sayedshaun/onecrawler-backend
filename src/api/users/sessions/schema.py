from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class OutSchema(BaseModel):
    """Base for response payloads: serializes Python snake_case fields as camelCase so
    the UI's existing `types.ts` interfaces can consume responses as-is."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )


class SessionOut(OutSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "8f14e45f-ceea-4d3a-8bd0-8a5f2b1c9e10",
                "createdAt": 1752480000000,
                "expiresAt": 1755072000000,
            }
        }
    )

    id: str
    created_at: int
    expires_at: int


class SessionListOut(OutSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "8f14e45f-ceea-4d3a-8bd0-8a5f2b1c9e10",
                        "createdAt": 1752480000000,
                        "expiresAt": 1755072000000,
                    }
                ]
            }
        }
    )

    items: list[SessionOut] = Field(default_factory=list)
