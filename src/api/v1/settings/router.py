import time
import uuid
from typing import get_args

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.security.dependencies import CurrentUser, get_current_user
from src.api.types import UuidPath
from src.api.v1.crawler.schema import GenAIProvider
from src.api.v1.settings.schema import (
    ApiKeyIn,
    ApiKeyOut,
    CrawlTemplateIn,
    CrawlTemplateListOut,
    CrawlTemplateOut,
)
from src.db.models import CrawlSettingsTemplate, ProviderApiKey
from src.db.pg import get_db

router = APIRouter(prefix="/settings", tags=["Settings"])

PROVIDERS: tuple[str, ...] = get_args(GenAIProvider)


# ---- crawl settings templates ----


@router.post(
    "/templates", response_model=CrawlTemplateOut, status_code=status.HTTP_201_CREATED
)
async def create_crawl_template(
    payload: CrawlTemplateIn,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    template = CrawlSettingsTemplate(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=payload.name,
        settings=payload.settings.model_dump(),
        filters=payload.filters.model_dump() if payload.filters else None,
        created_at=int(time.time() * 1000),
        updated_at=int(time.time() * 1000),
    )
    db.add(template)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template '{payload.name}' already exists",
        )

    await db.refresh(template)
    return template


@router.get("/templates", response_model=CrawlTemplateListOut)
async def list_crawl_templates(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    result = await db.execute(
        select(CrawlSettingsTemplate)
        .where(CrawlSettingsTemplate.user_id == current_user.id)
        .order_by(CrawlSettingsTemplate.name)
    )
    items = list(result.scalars().all())
    return CrawlTemplateListOut(items=items, total=len(items))


@router.get("/templates/{template_id}", response_model=CrawlTemplateOut)
async def get_crawl_template(
    template_id: UuidPath,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    template = await db.scalar(
        select(CrawlSettingsTemplate).where(
            CrawlSettingsTemplate.id == template_id,
            CrawlSettingsTemplate.user_id == current_user.id,
        )
    )
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )
    return template


@router.put("/templates/{template_id}", response_model=CrawlTemplateOut)
async def update_crawl_template(
    template_id: UuidPath,
    payload: CrawlTemplateIn,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    template = await db.scalar(
        select(CrawlSettingsTemplate).where(
            CrawlSettingsTemplate.id == template_id,
            CrawlSettingsTemplate.user_id == current_user.id,
        )
    )
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )

    template.name = payload.name
    template.settings = payload.settings.model_dump()
    template.filters = payload.filters.model_dump() if payload.filters else None
    template.updated_at = int(time.time() * 1000)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template '{payload.name}' already exists",
        )

    await db.refresh(template)
    return template


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_crawl_template(
    template_id: UuidPath,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    template = await db.scalar(
        select(CrawlSettingsTemplate).where(
            CrawlSettingsTemplate.id == template_id,
            CrawlSettingsTemplate.user_id == current_user.id,
        )
    )
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )
    await db.delete(template)
    await db.commit()


# ---- provider API keys ----


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_provider_api_keys(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    result = await db.execute(
        select(ProviderApiKey).where(ProviderApiKey.user_id == current_user.id)
    )
    keys = {row.provider: row for row in result.scalars().all()}
    return [
        ApiKeyOut(
            provider=provider,
            has_key=provider in keys,
            updated_at=keys[provider].updated_at if provider in keys else None,
        )
        for provider in PROVIDERS
    ]


@router.put("/api-keys/{provider}", response_model=ApiKeyOut)
async def set_provider_api_key(
    provider: str,
    payload: ApiKeyIn,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    if provider not in PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown provider: {provider}",
        )
    key = await db.get(ProviderApiKey, (current_user.id, provider))
    if key is None:
        key = ProviderApiKey(
            user_id=current_user.id,
            provider=provider,
            api_key=payload.api_key,
            updated_at=int(time.time() * 1000),
        )
        db.add(key)
    else:
        key.api_key = payload.api_key
        key.updated_at = int(time.time() * 1000)
    await db.commit()
    await db.refresh(key)
    return ApiKeyOut(provider=provider, has_key=True, updated_at=key.updated_at)


@router.delete("/api-keys/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_provider_api_key(
    provider: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    if provider not in PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown provider: {provider}",
        )
    key = await db.get(ProviderApiKey, (current_user.id, provider))
    if key is not None:
        await db.delete(key)
        await db.commit()
