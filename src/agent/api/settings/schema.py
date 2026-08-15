from pydantic import BaseModel, Field


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
