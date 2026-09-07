"""Agent construction and caching."""

from collections import OrderedDict

from deepharness import Agent, Budget

from . import tracing
from .llm import build_chat_model
from .prompt import SYSTEM_PROMPT
from .tools import TOOLS, EventToolbox

_MAX_CACHED_AGENTS = 128
_MAX_STEPS = 25

_agent_cache: OrderedDict[tuple[str, str, str | None, str | None], Agent] = (
    OrderedDict()
)


def get_agent(
    provider: str, model: str, api_key: str | None, base_url: str | None = None
) -> Agent:
    """Return an agent for the given provider/model/api_key/base_url, building and
    caching it on first use. They must already be resolved (see
    agent/router.py::_resolve_agent_settings) — this service has no shared fallback
    brain; every call is backed by a user's own saved LLM settings. Cache is bounded
    (LRU) since api_key varies per user in a multi-tenant setup and would otherwise
    grow unbounded.

    The agent holds no per-request state: the transcript is passed in per run and the
    auth token rides in deps, so one instance is safe to share across users.
    """
    key = (provider, model, api_key, base_url)

    if key in _agent_cache:
        _agent_cache.move_to_end(key)
        return _agent_cache[key]

    chat_model = build_chat_model(*key)
    agent = Agent(
        tracing.TracedLLM(chat_model, f"{provider}/{model}")
        if tracing.ENABLED
        else chat_model,
        tools=tracing.TracedToolbox(TOOLS) if tracing.ENABLED else EventToolbox(TOOLS),
        system=SYSTEM_PROMPT,
        name="onecrawler",
        budget=Budget(steps=_MAX_STEPS),
    )
    _agent_cache[key] = agent
    if len(_agent_cache) > _MAX_CACHED_AGENTS:
        _agent_cache.popitem(last=False)

    return agent
