# LLM Agent

A [deepharness](https://sayedshaun.github.io/deepharness/) agent that drives this same REST
API via LLM tool calling — think "chat with your crawler." It runs **in-process** inside
the `fastapi` container; there is no separate agent service or port.

## How it fits together

```
src/api/v1/agent/    chat + agent-settings endpoints (FastAPI layer)
src/agent/           the agent engine
  executor.py           builds/caches an Agent per (provider, model, api_key, base_url)
  tools.py              one tool per OneCrawler REST endpoint, plus web_search;
                        AgentDeps (per-request scope) and EventToolbox (stream events)
  llm.py                provider -> deepharness provider
  tracing.py            MLflow spans around model and tool calls
  prompt.py             system prompt
  core/client.py         thin HTTP client tools use to call this same API
```

- **Endpoints** live under `/api/v1` alongside the rest of the API — `src/api/v1/agent/router.py`
  authenticates with the same `CurrentUser`/`get_current_user` dependency as every other
  v1 route (no separate auth path).
- **Conversation history** (`AgentSettings`, `Conversation`, `ChatMessage`) is stored in
  the main Postgres database, in `src/db/models.py`, migrated by the same Alembic history
  as everything else — no separate database or `DeclarativeBase`.
- **Agent working memory** is the `ChatMessage` rows themselves: deepharness has no
  server-side checkpointer, so each run replays the conversation's stored human/ai turns
  (`helper.py::history_messages`) ahead of the new message. Earlier tool calls and their
  results are not stored, so the model sees what it said, not how it got there.
- **Tools** call back into this same API over HTTP (`src/agent/core/client.py::OneCrawlerClient`),
  forwarding the caller's own JWT — so every tool call runs with the calling user's
  permissions, not a shared service account.
- **Experiment tracking**: hand-written MLflow spans in `src/agent/tracing.py`, since
  no autolog integration can hook deepharness (it has no SDK to patch — it POSTs to each
  vendor's REST API directly). One `agent_run` span per chat turn, a `CHAT_MODEL` span
  with token usage per completion (`TracedLLM`), and a `TOOL` span per tool call
  (`TracedToolbox`). Tracing is off when `MLFLOW_TRACKING_URI` is empty.

## Endpoints — `/api/v1/chat`, `/api/v1/settings/agent`

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/v1/chat` | Send a message to the agent, get the full reply |
| POST | `/api/v1/chat/stream` | Same, streamed as Server-Sent Events (tokens + tool calls) |
| GET | `/api/v1/chats` | List this user's conversations |
| GET | `/api/v1/chats/{conversation_id}` | Full message history for one conversation |
| GET/PUT/DELETE | `/api/v1/settings/agent` | Get/save/clear this user's LLM + search provider config |

`PUT /api/v1/settings/agent` is required before `/chat` works — the agent has no shared
fallback LLM key; every call is backed by the calling user's own saved `llm.provider` /
`llm.model` / `llm.api_key`. `search` (a Tavily key) is optional and only needed for the
`web_search` tool.

`llm.provider` is `openai`, `anthropic`, `google`, `openrouter`, or `openai_compatible`
for a self-hosted OpenAI-compatible server (llama.cpp, vLLM, LM Studio, Ollama). That
last one takes an `llm.base_url` instead of a key, and `llm.model` is optional since such
a server serves whatever model it was started with:

```json
{"llm": {"provider": "openai_compatible", "base_url": "http://localhost:8080/v1"}}
```

## Configuration

Shares `src/core/config.py` — no separate config file or env prefix.

| Variable | Purpose | Default |
| --- | --- | --- |
| `MLFLOW_TRACKING_URI` | Where agent runs are reported; empty disables tracing | `http://mlflow:5000` |
| `MLFLOW_EXPERIMENT_NAME` | MLflow experiment name | `onecrawler-agents` |
| `AGENT_API_BASE_URL` | Base URL the agent's tools call back into this same API at | `http://localhost:8000/api/v1` |

## Adding a tool

Tools live in `src/agent/tools.py` as `@tool`-decorated async functions, each calling one
`OneCrawlerClient` method. A leading `ctx: Ctx` parameter (hidden from the model) carries
the caller's `auth_token` and optional `search_api_key` via `AgentDeps`, built per-request
in `agent_deps()`, `src/api/v1/agent/helper.py`. Register a new tool in the `TOOLS` list at
the bottom of the file — nothing else needs to change for the agent to pick it up.
