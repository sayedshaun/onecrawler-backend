from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.security.dependencies import CurrentUser, get_current_user
from src.api.users.account.schema import (
    ChangeEmailRequest,
    ChangePasswordOut,
    ChangePasswordRequest,
    RenameRequest,
)
from src.api.users.register.schema import UserOut
from src.core.security import hash_password, verify_password
from src.db.models import Users
from src.db.pg import get_db

router = APIRouter()


@router.get("/me", response_model=UserOut)
async def get_me(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    user = await db.get(Users, current_user.id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


@router.patch("/me/name", response_model=UserOut)
async def rename(
    payload: RenameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    user = await db.get(Users, current_user.id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    user.name = payload.name
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/me/email", response_model=UserOut)
async def change_email(
    payload: ChangeEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    user = await db.get(Users, current_user.id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password"
        )

    existing = await db.scalar(select(Users).where(Users.email == payload.email))
    if existing is not None and existing.id != user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    user.email = payload.email
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/me/password", response_model=ChangePasswordOut)
async def change_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    user = await db.get(Users, current_user.id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password"
        )

    user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    return ChangePasswordOut(detail="Password updated")
