from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.pool import get_arq_pool
from src.core.security import decode_access_token
from src.db.models import Users
from src.db.pg import get_db

_bearer_scheme = HTTPBearer()


@dataclass
class CurrentUser:
    id: str
    email: str
    user_type: str
    name: str
    jti: str
    exp: int


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
    )

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise unauthorized

    jti = payload.get("jti")
    redis = await get_arq_pool()
    if jti and await redis.exists(f"blocklist:{jti}"):
        raise unauthorized

    user = await db.get(Users, payload.get("sub"))
    if user is None or not user.is_active:
        raise unauthorized

    return CurrentUser(
        id=user.id,
        email=user.email,
        user_type=user.user_type,
        name=user.name,
        jti=jti,
        exp=payload["exp"],
    )
