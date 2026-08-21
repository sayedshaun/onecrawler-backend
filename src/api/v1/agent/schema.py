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
        "fallback key — see PUT /api/v1/settings/agent).",
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


class LLMConfigIn(BaseModel):
    provider: str = Field(..., description="openai, anthropic, google, or openrouter.")
    model: str = Field(..., description="Model name for that provider.")
    api_key: str = Field(..., description="Your own API key for that provider.")


class SearchConfigIn(BaseModel):
    provider: str = Field("tavily", description="Search provider. Only tavily today.")
    api_key: str = Field(..., description="Your own API key for that provider.")


class AgentSettingsIn(BaseModel):
    llm: LLMConfigIn | None = Field(
        None, description="Omit to leave your saved LLM config untouched."
    )
    search: SearchConfigIn | None = Field(
        None, description="Omit to leave your saved search config untouched."
    )


class LLMConfigOut(BaseModel):
    provider: str | None = None
    model: str | None = None
    has_key: bool = False


class SearchConfigOut(BaseModel):
    provider: str | None = None
    has_key: bool = False


class AgentSettingsOut(BaseModel):
    llm: LLMConfigOut
    search: SearchConfigOut
    updated_at: str | None = None
