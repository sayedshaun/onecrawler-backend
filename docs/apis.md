# API Reference

Full interactive docs (with request/response schemas and a "Try it out" console) are
served at `/docs` (Swagger UI) and `/redoc`; the raw OpenAPI spec is at `/openapi.json`.
This page is a quick index of every route grouped by area.

## Misc

| Method | Path | Description |
| --- | --- | --- |
| GET | `/` | Liveness message |
| GET | `/api/health` | Health check |
| GET | `/api/verify` | Verify a token / fetch the current user |

## Users & Auth — `/api/users`

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/users/register` | Create a user |
| POST | `/api/users/login` | Authenticate, get an access + refresh token |
| POST | `/api/users/logout` | Revoke the current access token (and refresh session, if provided) |
| POST | `/api/users/refresh` | Rotate a refresh token for a new access/refresh pair |
| GET | `/api/users/me` | Get the current user's profile |
| PATCH | `/api/users/me/name` | Rename the current user |
| PATCH | `/api/users/me/email` | Change email (requires current password) |
| PATCH | `/api/users/me/password` | Change password (requires current password; revokes all sessions) |
| GET | `/api/users/me/usage` | Crawl job / URL usage stats |
| GET | `/api/users/me/sessions` | List active refresh-token sessions |
| DELETE | `/api/users/me/sessions/{session_id}` | Revoke one session |
| POST | `/api/users/me/sessions/revoke-all` | Revoke all sessions ("log out everywhere") |

## Crawls — `/api/v1/crawls`

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/v1/crawls` | Create and enqueue a crawl job |
| GET | `/api/v1/crawls` | List crawl jobs (filter/paginate) |
| GET | `/api/v1/crawls/{job_id}` | Get a crawl job's detail + throughput history |
| GET | `/api/v1/crawls/{job_id}/download` | Download a job's results as JSON |
| GET | `/api/v1/crawls/{job_id}/logs` | Get a job's logs |
| GET | `/api/v1/crawls/{job_id}/discovered` | List URLs a job discovered |
| DELETE | `/api/v1/crawls/{job_id}/discovered/{discovered_id}` | Delete a discovered URL |
| POST | `/api/v1/crawls/{job_id}/scrape` | Scrape a job's discovered URLs as a new job |
| POST | `/api/v1/crawls/{job_id}/cancel` | Cancel a queued/running job |
| POST | `/api/v1/crawls/{job_id}/retry` | Re-run a failed job with the same settings |
| DELETE | `/api/v1/crawls/{job_id}` | Delete a crawl job (must not be active) |

## Dashboard & Data — `/api/v1/dashboard`, `/api/v1/data`

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/v1/dashboard/overview` | Aggregate stats for the dashboard |
| GET | `/api/v1/data` | List/search extracted result items |
| GET | `/api/v1/data/{result_id}` | Get one extracted result item |
| GET | `/api/v1/data/{result_id}/download` | Download a result item's content as JSON |

## Settings — `/api/v1/settings`

| Method | Path | Description |
| --- | --- | --- |
| GET/POST/PUT/DELETE | `/api/v1/settings/templates[/{id}]` | Crawl setting templates |
| GET/PUT/DELETE | `/api/v1/settings/api-keys[/{provider}]` | Stored GenAI provider API keys |

## Agent — `/api/v1/chat`, `/api/v1/settings/agent`

See [agent.md](agent.md) for architecture; routes below. `PUT /api/v1/settings/agent` is
required before `/chat` works.

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/v1/chat` | Send a message to the agent, get the full reply |
| POST | `/api/v1/chat/stream` | Same, streamed as Server-Sent Events (tokens + tool calls) |
| GET | `/api/v1/chats` | List this user's conversations |
| GET | `/api/v1/chats/{conversation_id}` | Full message history for one conversation |
| GET/PUT/DELETE | `/api/v1/settings/agent` | Get/save/clear this user's LLM + search provider config |
