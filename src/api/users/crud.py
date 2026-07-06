import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.security import hash_password
from src.db.models import Users


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[Users]:
    result = await db.execute(select(Users).where(Users.email == email))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    hashed_password: str,
    name: str = "",
    user_type: str = "user",
) -> Users:
    user = Users(
        id=str(uuid.uuid4()),
        name=name,
        email=email,
        hashed_password=hashed_password,
        user_type=user_type,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def ensure_default_admin(db: AsyncSession) -> None:
    """Seed the default admin account on startup if it doesn't exist yet."""
    existing = await get_user_by_email(db, settings.DEFAULT_ADMIN_EMAIL)
    if existing is not None:
        return

    await create_user(
        db,
        email=settings.DEFAULT_ADMIN_EMAIL,
        hashed_password=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
        name=settings.DEFAULT_ADMIN_NAME,
        user_type="admin",
    )
