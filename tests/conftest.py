import os

# Must run before the first `from src.core.config import settings` anywhere in the
# process — pydantic-settings reads these as env-var overrides on top of .env, and
# Settings() is a module-level singleton built at import time.
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5433")
os.environ.setdefault("POSTGRES_DB", "onecrawler_test")
os.environ.setdefault("POSTGRES_USER", "onecrawler")
os.environ.setdefault("POSTGRES_PASSWORD", "onecrawler")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")

import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.security.dependencies import CurrentUser, get_current_user
from src.api.v1.agent.router import router as agent_router
from src.db.base import Base
from src.db.models import AgentSettings, ChatMessage, Conversation, Users
from src.db.pg import async_session, engine, get_db


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    yield
    async with async_session() as session:
        await session.execute(delete(ChatMessage))
        await session.execute(delete(Conversation))
        await session.execute(delete(AgentSettings))
        await session.execute(delete(Users))
        await session.commit()


@pytest_asyncio.fixture
async def current_user() -> CurrentUser:
    async with async_session() as session:
        user = Users(
            id=str(uuid.uuid4()),
            name="Test User",
            email=f"test-{uuid.uuid4()}@example.com",
            hashed_password="not-a-real-hash",
            user_type="user",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return CurrentUser(
        id=user.id,
        email=user.email,
        user_type=user.user_type,
        name=user.name,
        jti="test-jti",
        exp=9999999999,
    )


async def _override_get_db() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def app(current_user: CurrentUser) -> FastAPI:
    application = FastAPI()
    application.include_router(agent_router, prefix="/api/v1")
    application.dependency_overrides[get_db] = _override_get_db
    application.dependency_overrides[get_current_user] = lambda: current_user
    return application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer test-token"},
    ) as ac:
        yield ac
