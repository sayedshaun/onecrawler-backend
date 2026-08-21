# LLM Agent

A LangGraph deep agent that drives this same REST API via LLM tool calling — think
"chat with your crawler." It runs **in-process** inside the `fastapi` container; there
is no separate agent service or port.

## How it fits together

```
src/api/v1/agent/    chat + agent-settings endpoints (FastAPI layer)
src/agent/           the agent engine
  executor.py           builds/caches a deep agent per (provider, model, api_key)
  tools.py              one tool per OneCrawler REST endpoint, plus web_search
  llm.py                provider -> langchain chat model
  prompt.py             system prompt
  core/client.py         thin HTTP client tools use to call this same API
```

- **Endpoints** live under `/api/v1` alongside the rest of the API — `src/api/v1/agent/router.py`
  authenticates with the same `CurrentUser`/`get_current_user` dependency as every other
  v1 route (no separate auth path).
- **Conversation history** (`AgentSettings`, `Conversation`, `ChatMessage`) is stored in
  the main Postgres database, in `src/db/models.py`, migrated by the same Alembic history
  as everything else — no separate database or `DeclarativeBase`.
- **Agent working memory** (LangGraph's own checkpoint state, separate from the chat-history
  tables above) is persisted via `langgraph-checkpoint-postgres`, set up once in `main.py`'s
  `lifespan` and handed to `src/agent/executor.py::set_checkpointer`.
- **Tools** call back into this same API over HTTP (`src/agent/core/client.py::OneCrawlerClient`),
  forwarding the caller's own JWT — so every tool call runs with the calling user's
  permissions, not a shared service account.
- **Experiment tracking**: `mlflow.langchain.autolog()` reports every agent run to the
  `mlflow` service.

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

## Configuration

Shares `src/core/config.py` — no separate config file or env prefix.

| Variable | Purpose | Default |
| --- | --- | --- |
| `MLFLOW_TRACKING_URI` | Where agent runs are reported | `http://mlflow:5000` |
| `MLFLOW_EXPERIMENT_NAME` | MLflow experiment name | `onecrawler-agents` |
| `AGENT_API_BASE_URL` | Base URL the agent's tools call back into this same API at | `http://localhost:8000/api/v1` |

`CHECKPOINTER_DSN` (a `Settings` property, not an env var) derives the LangGraph
checkpointer's connection string from the existing `POSTGRES_*` values — `psycopg`
doesn't understand SQLAlchemy's `+asyncpg` driver suffix, so it's stripped.

## Adding a tool

Tools live in `src/agent/tools.py` as `@tool`-decorated async functions, each calling one
`OneCrawlerClient` method. `config: RunnableConfig` carries the caller's `auth_token` and
optional `search_api_key` (set per-request in `agent_config()`,
`src/api/v1/agent/helper.py`). Register a new tool in the `TOOLS` list at the bottom of
the file — nothing else needs to change for the agent to pick it up.
