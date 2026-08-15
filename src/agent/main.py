from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.agent.agents.executor import set_checkpointer
from src.agent.api.chat.router import router as chat_router
from src.agent.api.settings.router import router as settings_router
from src.agent.core.config import settings
from src.agent.db.pg import init_db

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with AsyncPostgresSaver.from_conn_string(
        settings.CHECKPOINTER_DSN
    ) as checkpointer:
        await checkpointer.setup()
        set_checkpointer(checkpointer)
        yield


app = FastAPI(title="OneCrawler Agent", lifespan=lifespan)


@app.get("/")
async def root() -> dict:
    return {"service": "onecrawler-agents-backend", "status": "ok"}


@app.get("/ui")
async def chat_ui() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.include_router(chat_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
