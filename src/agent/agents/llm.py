from langchain.chat_models import init_chat_model
from langchain_openai import ChatOpenAI

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

_PROVIDER_TO_LANGCHAIN = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "google_genai",
}


def build_chat_model(provider: str, model: str, api_key: str):
    """provider/model/api_key must already be resolved — this service has no
    shared fallback brain; every call is backed by a user's own saved LLM
    settings (PUT /api/settings/agent)."""
    if provider == "openrouter":
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=_OPENROUTER_BASE_URL,
            temperature=0,
        )

    if provider not in _PROVIDER_TO_LANGCHAIN:
        raise ValueError(
            f"Unsupported provider {provider!r}; expected one of "
            f"{sorted([*_PROVIDER_TO_LANGCHAIN, 'openrouter'])}"
        )

    return init_chat_model(
        model,
        model_provider=_PROVIDER_TO_LANGCHAIN[provider],
        api_key=api_key,
        temperature=0,
    )
