from fastapi import APIRouter

from src.api.users.login.router import router as login_router
from src.api.users.logout.router import router as logout_router
from src.api.users.register.router import router as register_router

router = APIRouter(tags=["users"])
# `prefix` must be passed to each include_router() call, not this constructor
# — see the identical note in app/api/v1/crawler/router.py.
router.include_router(register_router, prefix="/users")
router.include_router(login_router, prefix="/users")
router.include_router(logout_router, prefix="/users")
