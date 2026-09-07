from deepharness import Anthropic, Gemini, OpenAI, OpenRouter
from deepharness.providers.base import LLM

_PROVIDERS = ("openai", "anthropic", "google", "openrouter", "openai_compatible")

#: llama.cpp, vLLM and friends serve a single model and ignore the payload's model
#: field, so a saved config for them needn't name one.
DEFAULT_LOCAL_MODEL = "local-model"

#: deepharness always sends an Authorization header, and httpx rejects the
#: ``Bearer `` an empty key would produce — so key-less servers (which ignore the
#: header entirely) get a placeholder token instead.
_NO_API_KEY = "no-key"


def build_chat_model(
    provider: str, model: str, api_key: str | None, base_url: str | None = None
) -> LLM:
    """provider/model/api_key must already be resolved — this service has no
    shared fallback brain; every call is backed by a user's own saved LLM
    settings (PUT /api/settings/agent). base_url is only used by (and required
    for) the openai_compatible provider: a self-hosted OpenAI-compatible server
    such as llama.cpp, vLLM or LM Studio, which usually needs no api key.

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
        case "openai_compatible":
            if not base_url:
                raise ValueError("openai_compatible requires a base_url")
            # A literal placeholder rather than None: None makes deepharness fall
            # back to OPENAI_API_KEY, which has nothing to do with a self-hosted
            # server.
            return OpenAI(
                model or DEFAULT_LOCAL_MODEL,
                api_key=api_key or _NO_API_KEY,
                base_url=base_url,
                temperature=0,
            )
    raise ValueError(
        f"Unsupported provider {provider!r}; expected one of {sorted(_PROVIDERS)}"
    )
