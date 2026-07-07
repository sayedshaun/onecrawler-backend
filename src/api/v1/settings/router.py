from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.settings import crud
from src.api.v1.settings.schema import (
    ApiKeyIn,
    ApiKeyOut,
    CrawlTemplateIn,
    CrawlTemplateListOut,
    CrawlTemplateOut,
)
from src.db.pg import get_db

router = APIRouter(prefix="/settings", tags=["Settings"])


def _require_provider(provider: str) -> None:
    if provider not in crud.PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")


@router.post(
    "/templates", response_model=CrawlTemplateOut, status_code=status.HTTP_201_CREATED
)
async def create_crawl_template(
    payload: CrawlTemplateIn, db: AsyncSession = Depends(get_db)
):
    try:
        template = await crud.create_template(
            db,
            name=payload.name,
            settings=payload.settings.model_dump(),
            filters=payload.filters.model_dump() if payload.filters else None,
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail=f"Template '{payload.name}' already exists"
        )

    return template


@router.get("/templates", response_model=CrawlTemplateListOut)
async def list_crawl_templates(db: AsyncSession = Depends(get_db)):
    items = await crud.list_templates(db)
    return CrawlTemplateListOut(items=items, total=len(items))


@router.get("/templates/{template_id}", response_model=CrawlTemplateOut)
async def get_crawl_template(template_id: str, db: AsyncSession = Depends(get_db)):
    template = await crud.get_template(db, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.put("/templates/{template_id}", response_model=CrawlTemplateOut)
async def update_crawl_template(
    template_id: str, payload: CrawlTemplateIn, db: AsyncSession = Depends(get_db)
):
    template = await crud.get_template(db, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        template = await crud.update_template(
            db,
            template,
            name=payload.name,
            settings=payload.settings.model_dump(),
            filters=payload.filters.model_dump() if payload.filters else None,
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail=f"Template '{payload.name}' already exists"
        )

    return template


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_crawl_template(template_id: str, db: AsyncSession = Depends(get_db)):
    template = await crud.get_template(db, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    await crud.delete_template(db, template)


# ---- provider API keys ----


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_provider_api_keys(db: AsyncSession = Depends(get_db)):
    keys = await crud.list_api_keys(db)
    return [
        ApiKeyOut(
            provider=provider,
            has_key=provider in keys,
            updated_at=keys[provider].updated_at if provider in keys else None,
        )
        for provider in crud.PROVIDERS
    ]


@router.put("/api-keys/{provider}", response_model=ApiKeyOut)
async def set_provider_api_key(
    provider: str, payload: ApiKeyIn, db: AsyncSession = Depends(get_db)
):
    _require_provider(provider)
    key = await crud.upsert_api_key(db, provider, payload.api_key)
    return ApiKeyOut(provider=provider, has_key=True, updated_at=key.updated_at)


@router.delete("/api-keys/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_provider_api_key(provider: str, db: AsyncSession = Depends(get_db)):
    _require_provider(provider)
    await crud.delete_api_key(db, provider)
