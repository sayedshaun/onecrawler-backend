from pydantic import BaseModel, ConfigDict, EmailStr
from pydantic.alias_generators import to_camel


class InSchema(BaseModel):
    """Base for request payloads: accepts the UI's snake_case fields as-is."""

    model_config = ConfigDict(extra="ignore")


class OutSchema(BaseModel):
    """Base for response payloads: serializes Python snake_case fields as camelCase
    so the UI's existing `types.ts` interfaces can consume responses as-is."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class LoginRequest(InSchema):
    email: EmailStr
    password: str


class TokenOut(OutSchema):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
