import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.security.dependencies import CurrentUser, get_current_user
from src.api.types import UuidPath
from src.api.users.sessions.schema import SessionListOut, SessionOut
from src.core.sessions import revoke_all_refresh_sessions
from src.db.models import RefreshSession
from src.db.pg import get_db

router = APIRouter()


@router.get("/me/sessions", response_model=SessionListOut)
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    now_ms = int(time.time() * 1000)
    result = await db.execute(
        select(RefreshSession)
        .where(
            RefreshSession.user_id == current_user.id,
            RefreshSession.revoked_at.is_(None),
            RefreshSession.expires_at > now_ms,
        )
        .order_by(RefreshSession.created_at.desc())
    )
    sessions = result.scalars().all()
    return SessionListOut(
        items=[
            SessionOut(id=s.jti, created_at=s.created_at, expires_at=s.expires_at)
            for s in sessions
        ]
    )


@router.delete("/me/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: UuidPath,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    session = await db.scalar(
        select(RefreshSession).where(
            RefreshSession.jti == session_id,
            RefreshSession.user_id == current_user.id,
        )
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    if session.revoked_at is None:
        session.revoked_at = int(time.time() * 1000)
        await db.commit()


@router.post("/me/sessions/revoke-all", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_all_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    await revoke_all_refresh_sessions(db, user_id=current_user.id)
    await db.commit()
