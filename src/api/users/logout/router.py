import time

from fastapi import APIRouter, Depends

from src.api.security.dependencies import CurrentUser, get_current_user
from src.api.users.logout.schema import LogoutOut
from src.core.pool import get_arq_pool

router = APIRouter()


@router.post("/logout", response_model=LogoutOut)
async def logout(current_user: CurrentUser = Depends(get_current_user)):
    redis = await get_arq_pool()
    ttl = max(current_user.exp - int(time.time()), 1)
    await redis.setex(f"blocklist:{current_user.jti}", ttl, "1")
    return LogoutOut(detail="Logged out")
