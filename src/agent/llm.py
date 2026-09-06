from deepharness import Anthropic, Gemini, OpenAI, OpenRouter
from deepharness.providers.base import LLM

_PROVIDERS = ("openai", "anthropic", "google", "openrouter")


def build_chat_model(provider: str, model: str, api_key: str) -> LLM:
    """provider/model/api_key must already be resolved — this service has no
    shared fallback brain; every call is backed by a user's own saved LLM
    settings (PUT /api/settings/agent).

    Note: deepharness's OpenAI-compatible payload has no max_tokens field, so the
    3000-token output cap the LangChain OpenRouter client used to carry (to keep
    requests inside a free-tier credit balance) can't be expressed here.
    """
    match provider:
        case "openai":
            return OpenAI(model, api_key=api_key, temperature=0)
        case "openrouter":
            return OpenRouter(model, api_key=api_key, temperature=0)
        case "anthropic":
            return Anthropic(model, api_key=api_key)
        case "google":
            return Gemini(model, api_key=api_key)
    raise ValueError(
        f"Unsupported provider {provider!r}; expected one of {sorted(_PROVIDERS)}"
    )
