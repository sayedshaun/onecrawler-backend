from fastapi import APIRouter, Depends

from src.api.security.dependencies import CurrentUser, get_current_user
from src.api.security.verify.schema import CurrentUserOut

router = APIRouter()


@router.get("/verify", response_model=CurrentUserOut)
async def verify_token(current_user: CurrentUser = Depends(get_current_user)):
    return CurrentUserOut(
        id=current_user.id, name=current_user.name, email=current_user.email, user_type=current_user.user_type
    )
