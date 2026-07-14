from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.security.dependencies import CurrentUser, get_current_user
from src.api.users.account.schema import (
    ChangeEmailRequest,
    ChangePasswordOut,
    ChangePasswordRequest,
    RenameRequest,
    UsageOut,
)
from src.api.users.register.schema import UserOut
from src.api.v1.dashboard.schema import JobCountsOut
from src.core.security import hash_password, verify_password
from src.db.models import CrawlJob, CrawlStatus, Users
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


@router.get("/me/usage", response_model=UsageOut)
async def get_usage(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    status_result = await db.execute(
        select(CrawlJob.status, func.count())
        .where(CrawlJob.user_id == current_user.id)
        .group_by(CrawlJob.status)
    )
    job_counts = {status: 0 for status in CrawlStatus}
    for job_status, count in status_result.all():
        job_counts[job_status] = count

    url_row = await db.execute(
        select(
            func.coalesce(func.sum(CrawlJob.urls_discovered), 0),
            func.coalesce(func.sum(CrawlJob.urls_scraped), 0),
            func.coalesce(func.sum(CrawlJob.urls_failed), 0),
        ).where(CrawlJob.user_id == current_user.id)
    )
    urls_discovered, urls_scraped, urls_failed = url_row.one()

    total_jobs = await db.scalar(
        select(func.count())
        .select_from(CrawlJob)
        .where(CrawlJob.user_id == current_user.id)
    )

    now = datetime.now(UTC)
    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    this_month = CrawlJob.created_at >= int(month_start.timestamp() * 1000)

    jobs_this_month = await db.scalar(
        select(func.count())
        .select_from(CrawlJob)
        .where(CrawlJob.user_id == current_user.id, this_month)
    )
    urls_scraped_this_month = await db.scalar(
        select(func.coalesce(func.sum(CrawlJob.urls_scraped), 0)).where(
            CrawlJob.user_id == current_user.id, this_month
        )
    )

    return UsageOut(
        total_jobs=total_jobs,
        job_counts=JobCountsOut(**job_counts),
        urls_discovered=int(urls_discovered),
        urls_scraped=int(urls_scraped),
        urls_failed=int(urls_failed),
        jobs_this_month=jobs_this_month,
        urls_scraped_this_month=int(urls_scraped_this_month),
    )
