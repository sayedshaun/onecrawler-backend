from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class InSchema(BaseModel):
    """Base for request payloads: accepts the UI's snake_case fields as-is."""

    model_config = ConfigDict(extra="ignore")


class OutSchema(BaseModel):
    """Base for response payloads: serializes Python snake_case fields as camelCase so
    the UI's existing `types.ts` interfaces can consume responses as-is."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )


class RefreshRequest(InSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"refresh_token": "8f14e45f-ceea-4d3a-8bd0-8a5f2b1c9e10"}
        }
    )

    refresh_token: str


class RefreshOut(OutSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refreshToken": "9e14e45f-ceea-4d3a-8bd0-8a5f2b1c9e11",
                "tokenType": "bearer",
                "expiresIn": 3600,
            }
        }
    )

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
