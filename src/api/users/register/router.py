from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.users import crud
from src.api.users.register.schema import RegisterRequest, UserOut
from src.core.security import hash_password
from src.db.pg import get_db

router = APIRouter()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await crud.get_user_by_email(db, payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    user = await crud.create_user(
        db,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        name=payload.name,
    )
    return user
