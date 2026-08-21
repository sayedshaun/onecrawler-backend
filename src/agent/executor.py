from collections import OrderedDict
from typing import Any

import mlflow
from deepagents import create_deep_agent

from src.core.config import settings

from .llm import build_chat_model
from .prompt import SYSTEM_PROMPT
from .tools import TOOLS

mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
mlflow.set_experiment(settings.MLFLOW_EXPERIMENT_NAME)
mlflow.langchain.autolog()

_MAX_CACHED_AGENTS = 128

_checkpointer = None
_agent_cache: OrderedDict[tuple[str, str, str], Any] = OrderedDict()


def set_checkpointer(checkpointer) -> None:
    """Called once from the app's lifespan once a checkpointer connection is open."""
    global _checkpointer
    _checkpointer = checkpointer
    _agent_cache.clear()


def get_agent(provider: str, model: str, api_key: str) -> Any:
    """Return a deep agent for the given provider/model/api_key, building and
    caching it on first use. provider/model/api_key must already be resolved
    (see chat/router.py::_resolve_llm_config) — this service has no shared
    fallback brain; every call is backed by a user's own saved LLM settings.
    Cache is bounded (LRU) since api_key varies per user in a multi-tenant
    setup and would otherwise grow unbounded."""
    key = (provider, model, api_key)

    if key in _agent_cache:
        _agent_cache.move_to_end(key)
        return _agent_cache[key]

    agent = create_deep_agent(
        model=build_chat_model(*key),
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=_checkpointer,
    )
    _agent_cache[key] = agent
    if len(_agent_cache) > _MAX_CACHED_AGENTS:
        _agent_cache.popitem(last=False)

    return agent
