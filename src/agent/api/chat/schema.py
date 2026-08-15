from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="Natural-language instruction for the agent.")
    conversation_id: str = Field(
        ...,
        description="Stable id used to persist and resume this conversation's history.",
    )
    provider: str | None = Field(
        None,
        description="Override your saved LLM provider (openai, anthropic, google, "
        "openrouter) for this call only — doesn't change your saved settings. Only "
        "takes effect if it matches your saved provider's key (there's no shared "
        "fallback key — see PUT /api/settings/agent).",
    )
    model: str | None = Field(
        None, description="Override the model name for this call only."
    )


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str


class ConversationOut(BaseModel):
    conversation_id: str
    title: str
    updated_at: str


class ChatMessageOut(BaseModel):
    role: str
    content: str
    created_at: str


class ConversationDetailOut(ConversationOut):
    messages: list[ChatMessageOut]
