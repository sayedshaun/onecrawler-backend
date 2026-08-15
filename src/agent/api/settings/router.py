from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import AgentSettings
from ...db.pg import get_db
from ..deps import bearer_token, verified_user
from .schema import (
    AgentSettingsIn,
    AgentSettingsOut,
    LLMConfigOut,
    SearchConfigOut,
)

router = APIRouter(tags=["Settings"])


def _to_out(row: AgentSettings | None) -> AgentSettingsOut:
    if row is None:
        return AgentSettingsOut(llm=LLMConfigOut(), search=SearchConfigOut())
    return AgentSettingsOut(
        llm=LLMConfigOut(
            provider=row.llm_provider,
            model=row.llm_model,
            has_key=row.llm_api_key is not None,
        ),
        search=SearchConfigOut(
            provider=row.search_provider,
            has_key=row.search_api_key is not None,
        ),
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


@router.put("/settings/agent", response_model=AgentSettingsOut)
async def set_agent_settings(
    payload: AgentSettingsIn,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> AgentSettingsOut:
    """Save this user's agent config. llm and search are independent — send
    just one to update only that part, or both together. llm is required
    before /chat works; search is optional, only needed for web_search."""
    if payload.llm is None and payload.search is None:
        raise HTTPException(422, detail="Provide at least one of llm or search.")

    user = await verified_user(bearer_token(authorization))

    update: dict = {}
    if payload.llm is not None:
        update["llm_provider"] = payload.llm.provider
        update["llm_model"] = payload.llm.model
        update["llm_api_key"] = payload.llm.api_key
    if payload.search is not None:
        update["search_provider"] = payload.search.provider
        update["search_api_key"] = payload.search.api_key

    stmt = (
        pg_insert(AgentSettings)
        .values(user_id=user["id"], **update)
        .on_conflict_do_update(index_elements=[AgentSettings.user_id], set_=update)
    )
    await db.execute(stmt)
    await db.commit()

    result = await db.execute(
        select(AgentSettings).where(AgentSettings.user_id == user["id"])
    )
    return _to_out(result.scalar_one_or_none())


@router.get("/settings/agent", response_model=AgentSettingsOut)
async def get_agent_settings(
    authorization: str = Header(...), db: AsyncSession = Depends(get_db)
) -> AgentSettingsOut:
    """Status only — never returns raw api_keys."""
    user = await verified_user(bearer_token(authorization))

    result = await db.execute(
        select(AgentSettings).where(AgentSettings.user_id == user["id"])
    )
    return _to_out(result.scalar_one_or_none())


@router.delete("/settings/agent", status_code=204)
async def clear_agent_settings(
    scope: str | None = Query(
        None, description="'llm', 'search', or omit to clear both."
    ),
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> None:
    if scope not in (None, "llm", "search"):
        raise HTTPException(422, detail="scope must be 'llm', 'search', or omitted.")

    user = await verified_user(bearer_token(authorization))

    result = await db.execute(
        select(AgentSettings).where(AgentSettings.user_id == user["id"])
    )
    row = result.scalar_one_or_none()
    if row is None:
        return

    if scope is None:
        await db.delete(row)
    elif scope == "llm":
        row.llm_provider = row.llm_model = row.llm_api_key = None
    else:
        row.search_provider = row.search_api_key = None
    await db.commit()
