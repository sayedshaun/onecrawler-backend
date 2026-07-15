from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class OutSchema(BaseModel):
    """Base for response payloads: serializes Python snake_case fields as camelCase so
    the UI's existing `types.ts` interfaces can consume responses as-is."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )


class CurrentUserOut(OutSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "8f14e45f-ceea-4d3a-8bd0-8a5f2b1c9e10",
                "name": "Jane Doe",
                "email": "jane.doe@example.com",
                "userType": "standard",
            }
        }
    )

    id: str
    name: str
    email: str
    user_type: str
