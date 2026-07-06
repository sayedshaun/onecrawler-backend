from fastapi import APIRouter

from src.api.security.verify.router import router as verify_router

router = APIRouter(tags=["security"])
# `prefix` must be passed to each include_router() call, not this constructor
# — see the identical note in app/api/v1/crawler/router.py.
router.include_router(verify_router, prefix="/security")
