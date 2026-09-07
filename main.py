import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from src.api.security.router import router as security_router
from src.api.users.router import router as users_router
from src.api.v1.router import api_router
from src.core.config import settings
from src.core.logger import get_logger
from src.core.pool import close_arq_pool, get_arq_pool
from src.core.security import hash_password
from src.db.models import Users
from src.db.pg import async_session

get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_session() as db:
        admin = await db.scalar(
            select(Users).where(Users.email == settings.DEFAULT_ADMIN_EMAIL)
        )
        if admin is None:
            db.add(
                Users(
                    id=str(uuid.uuid4()),
                    name=settings.DEFAULT_ADMIN_NAME,
                    email=settings.DEFAULT_ADMIN_EMAIL,
                    hashed_password=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                    user_type="admin",
                )
            )
            await db.commit()
    await get_arq_pool()
    yield
    await close_arq_pool()


app = FastAPI(title="OneCrawler API", lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "Welcome to OneCrawler API"}


@app.get("/api/health")
async def health():
    return {"status": "ok"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(users_router, prefix="/api")
app.include_router(security_router, prefix="/api")
app.include_router(api_router, prefix="/api/v1")
