from pydantic import BaseModel, Field, model_validator


class ChatRequest(BaseModel):
    message: str = Field(..., description="Natural-language instruction for the agent.")
    conversation_id: str = Field(
        ...,
        description="Stable id used to persist and resume this conversation's history.",
    )
    provider: str | None = Field(
        None,
        description="Override your saved LLM provider (openai, anthropic, google, "
        "openrouter, openai_compatible) for this call only — doesn't change your "
        "saved settings. Only takes effect if it matches your saved provider's key "
        "and base_url (there's no shared fallback key — see "
        "PUT /api/v1/settings/agent).",
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
    provider: str = Field(
        ...,
        description="openai, anthropic, google, openrouter, or openai_compatible "
        "for a self-hosted OpenAI-compatible server (llama.cpp, vLLM, LM Studio).",
    )
    model: str = Field(
        "",
        description="Model name for that provider. Optional (and usually ignored) "
        "for openai_compatible, which serves whatever model it was started with.",
    )
    api_key: str | None = Field(
        None,
        description="Your own API key for that provider. Required except for "
        "openai_compatible, which usually needs none.",
    )
    base_url: str | None = Field(
        None,
        description="Endpoint of your OpenAI-compatible server, e.g. "
        "http://localhost:8080/v1. Required for openai_compatible, ignored "
        "otherwise.",
    )

    @model_validator(mode="after")
    def _check_provider_requirements(self) -> "LLMConfigIn":
        if self.provider == "openai_compatible":
            if not self.base_url:
                raise ValueError("base_url is required for openai_compatible.")
            return self
        if not self.model:
            raise ValueError(f"model is required for provider {self.provider!r}.")
        if not self.api_key:
            raise ValueError(f"api_key is required for provider {self.provider!r}.")
        return self


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
    base_url: str | None = None


class SearchConfigOut(BaseModel):
    provider: str | None = None
    has_key: bool = False


class AgentSettingsOut(BaseModel):
    llm: LLMConfigOut
    search: SearchConfigOut
    updated_at: str | None = None
