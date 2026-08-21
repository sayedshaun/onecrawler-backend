from fastapi import APIRouter

from src.api.v1.agent.router import router as agent_router
from src.api.v1.crawler.router import router as crawler_router
from src.api.v1.dashboard.router import router as dashboard_router
from src.api.v1.data.router import router as data_router
from src.api.v1.settings.router import router as settings_router

api_router = APIRouter()
api_router.include_router(agent_router)
api_router.include_router(crawler_router)
api_router.include_router(dashboard_router)
api_router.include_router(data_router)
api_router.include_router(settings_router)
