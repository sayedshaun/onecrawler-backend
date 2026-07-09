# OneCrawler Backend

FastAPI backend for OneCrawler — a web crawling and content-extraction platform. It exposes a REST API for managing crawl jobs, settings, and extracted data, and drives the actual crawling/scraping work through an async job queue backed by [`onecrawler`](https://pypi.org/project/onecrawler/) (browser automation, link extraction, and content filters).

## Table of Contents

- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Logging](#logging)
- [Database Migrations](#database-migrations)
- [Authentication](#authentication)
- [API Reference](#api-reference)
- [Crawl Modes, Strategies & Filters](#crawl-modes-strategies--filters)
- [Development](#development)
- [Testing](#testing)
- [Deployment Notes](#deployment-notes)
- [Troubleshooting](#troubleshooting)

## Architecture

```mermaid
flowchart LR
    client[HTTP clients] --> fastapi["fastapi<br/>REST API: auth, CRUD, job creation"]
    fastapi -->|enqueues job| redis[("redis<br/>job queue")]
    fastapi <-->|reads/writes| postgres[("postgres<br/>jobs, users, results...")]
    redis -->|dequeues| arq["arq<br/>worker: runs crawls"]
    arq -->|writes results| postgres

    classDef default stroke:#666,stroke-width:1.5px
```

The API and worker are split into separate containers built from the same [Dockerfile](Dockerfile) with different targets:

- **`api`** — only enqueues jobs onto Redis via [arq](https://arq-docs.helpmanual.io/); it never imports `onecrawler` or launches a browser, so its image stays small.
- **`worker`** — actually drives `onecrawler` + Playwright, so it installs the full `onecrawler[genai]` extra and Chromium.

A one-off **`migrate`** service runs `alembic upgrade head` before `fastapi`/`arq` start (see [docker-compose.yml](docker-compose.yml)).

## Tech Stack

| Concern | Choice |
| --- | --- |
| Web framework | [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn |
| ORM / DB driver | SQLAlchemy 2.0 (async) + asyncpg |
| Database | PostgreSQL 16 |
| Job queue | [arq](https://arq-docs.helpmanual.io/) (Redis-backed) |
| Migrations | Alembic |
| Auth | JWT (PyJWT) + Argon2 password hashing |
| Validation / schemas | Pydantic v2 |
| Crawling engine | [`onecrawler`](https://pypi.org/project/onecrawler/) (Playwright-based) |
| Linting / formatting | ruff, ruff-format, docformatter (via pre-commit) |

Requires Python 3.12+.

## Project Structure

```
main.py                     FastAPI app entrypoint (lifespan, middleware, router mounts)
src/
  api/
    security/                JWT auth dependency (get_current_user) + /verify endpoint
    users/                    register / login / logout
    v1/
      crawler/                crawl job CRUD, filters, settings schema
      dashboard/               aggregate stats for the UI
      data/                    extracted result items
      settings/                 crawl setting templates + provider API keys
  core/
    config.py                 pydantic-settings Settings (reads .env)
    security.py                JWT + password hashing
    pool.py                     arq Redis connection pool
  db/
    models.py                   SQLAlchemy ORM models
    pg.py                        async engine/session
  worker/
    settings.py                  arq WorkerSettings
    settings_builder.py           maps a CrawlJob's JSON payload to onecrawler Settings/FilterChain
    tasks.py                      the actual crawl job (sitemap / link_extraction / crawler modes)
alembic/                        migrations
```

## Getting Started

### Prerequisites

- Docker + Docker Compose (recommended), **or** Python 3.12+, PostgreSQL 16, and Redis 7 if running natively.

### Quick start (Docker Compose)

```bash
cp .env.example .env
# edit .env — at minimum set a real JWT_SECRET_KEY before anything but local dev

docker compose up --build
```

This starts `postgres`, `redis`, runs migrations (`migrate`), then starts `fastapi` (http://localhost:8000) and the `arq` worker. A default admin user is seeded on first boot from `DEFAULT_ADMIN_*` in `.env`.

### Local development (live reload)

[`docker-compose.dev.yml`](docker-compose.dev.yml) bind-mounts the repo into the `fastapi`/`arq` containers and runs `uvicorn --reload`, so code edits apply without rebuilding:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

The `arq` worker doesn't hot-reload (job processes shouldn't restart mid-run) — restart it manually after worker-side changes:

```bash
docker compose restart arq
```

This dev overlay also starts an `ngrok` container that tunnels `fastapi` to a public URL — useful for testing webhooks or sharing a local build. Set `NGROK_AUTHTOKEN` in `.env` (get one from [dashboard.ngrok.com](https://dashboard.ngrok.com/get-started/your-authtoken)), then check the assigned URL at `http://localhost:4040`.

### Running without Docker

```bash
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e .[worker]        # omit [worker] if you only need the API
playwright install chromium --with-deps   # only needed to actually run crawls

cp .env.example .env   # point POSTGRES_HOST / REDIS_URL at your local services
alembic upgrade head
uvicorn main:app --reload
# in another shell:
arq src.worker.settings.WorkerSettings
```

## Configuration

All configuration is via environment variables (`.env`, loaded by `src/core/config.py`). See [`.env.example`](.env.example) for the full annotated list; the essentials:

| Variable | Purpose | Default |
| --- | --- | --- |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Postgres credentials | `onecrawler` |
| `POSTGRES_HOST` / `POSTGRES_PORT` | Postgres connection (compose service name in Docker) | `postgres` / `5432` |
| `REDIS_URL` | Redis connection for arq's job queue | `redis://redis:6379/0` |
| `JWT_SECRET_KEY` | Signing key for access tokens — **change this outside local dev** | `dev-secret-change-me` |
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime | `60` |
| `DEFAULT_ADMIN_NAME` / `_EMAIL` / `_PASSWORD` | Seeded admin account (only created if no user with that email exists) | see `.env.example` |
| `CORS_ORIGINS` | JSON array of allowed origins | `["http://localhost:5173"]` |
| `LOG_LEVEL` | Root logging level (`DEBUG`/`INFO`/`WARNING`/`ERROR`) for the API and worker | `INFO` |
| `POSTGRES_HOST_PORT` / `REDIS_HOST_PORT` / `API_HOST_PORT` | Host-side port overrides for docker-compose | commented out |
| `NGROK_AUTHTOKEN` | Dev-only: public tunnel token for `docker-compose.dev.yml`'s `ngrok` service | unset |

Generate a real `JWT_SECRET_KEY` with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## Logging

`src/core/logger.py` configures the root logger (via `get_logger()`, called on startup by both `main.py` and `src/worker/settings.py`) with two handlers:

- A rotating file handler at `logs/app.log`, capped at 20MB with 3 backups.
- A console handler (visible via `docker compose logs`).

The level is controlled by `LOG_LEVEL`. Note `logs/` isn't a mounted volume, so file logs are lost if a container is recreated (not just restarted) — use `docker compose logs` for anything you need to survive that.

## Database Migrations

Standard Alembic workflow:

```bash
alembic upgrade head                 # apply all migrations
alembic revision -m "description"    # create a new empty migration
alembic downgrade -1                 # roll back one revision
```

Migrations live in [`alembic/versions/`](alembic/versions/) and run automatically via the `migrate` service in `docker-compose.yml` before the API/worker start.

## Authentication

Auth is stateless JWT Bearer tokens (`Authorization: Bearer <token>`), issued by `POST /api/users/login` and validated by `HTTPBearer` (`src/api/security/dependencies.py`). Logout adds the token's `jti` to a Redis blocklist so it can't be reused before it expires.

**In Swagger (`/docs`):**
1. Call `POST /api/users/login` with your email/password (the seeded admin credentials are in `.env`).
2. Copy `accessToken` from the response.
3. Click **Authorize**, paste the raw token (no `Bearer ` prefix needed — Swagger adds it), and confirm.

## API Reference

Full interactive docs (with request/response schemas and a "Try it out" console) are served at `/docs` (Swagger UI) and `/redoc`; the raw OpenAPI spec is at `/openapi.json`.

| Method | Path | Description |
| --- | --- | --- |
| GET | `/` | Liveness message |
| GET | `/api/health` | Health check |
| POST | `/api/users/register` | Create a user |
| POST | `/api/users/login` | Get an access token |
| POST | `/api/users/logout` | Invalidate the current token |
| GET | `/api/verify` | Verify a token / fetch the current user |
| POST | `/api/v1/crawls` | Create a crawl job |
| GET | `/api/v1/crawls` | List crawl jobs |
| GET | `/api/v1/crawls/{job_id}` | Get a crawl job |
| DELETE | `/api/v1/crawls/{job_id}` | Delete a crawl job |
| GET | `/api/v1/crawls/{job_id}/logs` | Get a job's logs |
| GET | `/api/v1/crawls/{job_id}/discovered` | List URLs a job discovered |
| POST | `/api/v1/crawls/{job_id}/cancel` | Cancel a running job |
| GET | `/api/v1/dashboard/overview` | Aggregate stats for the dashboard |
| GET | `/api/v1/data` | List extracted result items |
| GET | `/api/v1/data/{result_id}` | Get one extracted result item |
| GET/POST/PUT/DELETE | `/api/v1/settings/templates[/{id}]` | Crawl setting templates |
| GET/PUT/DELETE | `/api/v1/settings/api-keys[/{provider}]` | Stored GenAI provider API keys |

## Crawl Modes, Strategies & Filters

A crawl job (`POST /api/v1/crawls`) picks one **mode**:

- `sitemap` — discovers URLs from a site's sitemap.
- `link_extraction` — follows links (`shallow` or `deep`) from the target URL.
- `crawler` — full crawl + content extraction, streaming results as `CrawlResultItem` rows.

For `crawler` mode, `scraping_strategy` controls how page content is turned into structured data:

- `heuristic` — fixed extraction fields (title, text, metadata) via `onecrawler`'s built-in parser.
- `genai` — an LLM extracts fields matching a caller-defined `output_schema` (arbitrary field names/types).

Because these two strategies produce differently-shaped output, `CrawlResultItem.content` is stored as `JSONB` rather than a fixed set of columns.

Optional `filters` (AND/OR trees of `FilterNodeIn` nodes) narrow which discovered pages get scraped: `by_date` (validated as `YYYY-MM-DD`), `by_keywords`, `by_files`, `by_extension`, `by_cosine_similarity`.

## Development

Pre-commit runs ruff (lint + import sorting + `X | None` typing), ruff-format, and docformatter (docstring wrapping):

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Follow [AGENTS.md](AGENTS.md) / [CLAUDE.md](CLAUDE.md) for code style conventions used throughout this repo.

## Testing

There is no automated test suite yet. Verify changes by exercising the running API — via Swagger (`/docs`), `curl`, or by tailing the worker's logs (`docker compose logs -f arq`) while a crawl job runs. When adding tests, prefer `pytest` + `httpx.AsyncClient` against the FastAPI app, and a real (containerized) Postgres/Redis over mocks.

## Deployment Notes

- The `api` and `worker` images are independent (see [Dockerfile](Dockerfile) targets) — deploy/scale them separately; only `worker` needs Playwright/Chromium.
- Run `alembic upgrade head` before starting new API/worker versions (the `migrate` service in `docker-compose.yml` models this as a one-off job that `fastapi`/`arq` wait on via `service_completed_successfully`).
- Set a real `JWT_SECRET_KEY` and rotate the seeded default admin password before exposing this beyond local dev.
- `CORS_ORIGINS` must list your actual frontend origin(s) in production.

## Troubleshooting

- **`alembic upgrade head` fails on a running container**: if you're iterating on a migration, copy the updated file into the container (`docker cp`) or rebuild the image — code isn't hot-reloaded unless you're using `docker-compose.dev.yml`'s bind mount.
- **Windows line endings**: the repo is LF-based; Git will warn about CRLF conversion on Windows checkouts — this is expected and harmless.
- **A crawl job fails immediately with a date-parsing error**: `filters` nodes of kind `by_date` require `start`/`end` in `YYYY-MM-DD` format; anything else is rejected at request time with a `422`.
