"""Malformed ids must be rejected as 422 before they reach a query.

Every id column is `UUID(as_uuid=False)`, so a non-UUID string used to travel all the
way to asyncpg and raise a DataError there — surfacing as a 500 rather than a 4xx.
"""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.security.dependencies import CurrentUser, get_current_user
from src.api.users.sessions.router import router as sessions_router
from src.api.v1.crawler.router import router as crawler_router
from src.api.v1.data.router import router as data_router
from src.api.v1.settings.router import router as settings_router
from src.db.pg import async_session, get_db

BAD_ID = "not-a-uuid"
ABSENT_ID = "00000000-0000-0000-0000-000000000000"

_SETTINGS = {
    "browser_settings": {"viewport": {"width": 1280, "height": 800}},
}

# (method, path template, json body) — the body only matters for routes that need one to
# get past request-body validation and reach the path-param check.
UUID_ROUTES = [
    ("GET", "/api/v1/settings/templates/{id}", None),
    ("PUT", "/api/v1/settings/templates/{id}", {"name": "x", "settings": _SETTINGS}),
    ("DELETE", "/api/v1/settings/templates/{id}", None),
    ("GET", "/api/v1/crawls/{id}", None),
    ("DELETE", "/api/v1/crawls/{id}", None),
    ("GET", "/api/v1/crawls/{id}/logs", None),
    ("GET", "/api/v1/crawls/{id}/discovered", None),
    ("GET", "/api/v1/crawls/{id}/download", None),
    ("POST", "/api/v1/crawls/{id}/cancel", None),
    ("POST", "/api/v1/crawls/{id}/retry", None),
    ("POST", "/api/v1/crawls/{id}/scrape", {"settings": _SETTINGS}),
    ("GET", "/api/v1/data/{id}", None),
    ("GET", "/api/v1/data/{id}/download", None),
    ("DELETE", "/api/users/me/sessions/{id}", None),
]


async def _override_get_db() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def v1_client(current_user: CurrentUser) -> AsyncIterator[AsyncClient]:
    application = FastAPI()
    application.include_router(sessions_router, prefix="/api/users")
    for router in (crawler_router, data_router, settings_router):
        application.include_router(router, prefix="/api/v1")
    application.dependency_overrides[get_db] = _override_get_db
    application.dependency_overrides[get_current_user] = lambda: current_user
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.parametrize(("method", "template", "body"), UUID_ROUTES)
async def test_malformed_id_returns_422(
    v1_client: AsyncClient, method: str, template: str, body: dict | None
) -> None:
    response = await v1_client.request(method, template.format(id=BAD_ID), json=body)
    assert response.status_code == 422


@pytest.mark.parametrize(("method", "template", "body"), UUID_ROUTES)
async def test_well_formed_but_absent_id_still_returns_404(
    v1_client: AsyncClient, method: str, template: str, body: dict | None
) -> None:
    response = await v1_client.request(method, template.format(id=ABSENT_ID), json=body)
    assert response.status_code == 404


async def test_malformed_nested_discovered_ids_return_422(
    v1_client: AsyncClient,
) -> None:
    for job_id, discovered_id in ((ABSENT_ID, BAD_ID), (BAD_ID, ABSENT_ID)):
        response = await v1_client.delete(
            f"/api/v1/crawls/{job_id}/discovered/{discovered_id}"
        )
        assert response.status_code == 422


async def test_malformed_job_id_query_filter_returns_422(
    v1_client: AsyncClient,
) -> None:
    response = await v1_client.get("/api/v1/data", params={"job_id": BAD_ID})
    assert response.status_code == 422

    ok_response = await v1_client.get("/api/v1/data", params={"job_id": ABSENT_ID})
    assert ok_response.status_code == 200


async def test_malformed_export_ids_return_422(v1_client: AsyncClient) -> None:
    for payload in ({"ids": [BAD_ID]}, {"job_id": BAD_ID}):
        response = await v1_client.post("/api/v1/data/export", json=payload)
        assert response.status_code == 422
