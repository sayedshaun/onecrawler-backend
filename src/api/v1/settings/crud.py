import time
import uuid
from typing import get_args

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.crawler.schema import GenAIProvider
from src.db.models import CrawlSettingsTemplate, ProviderApiKey

PROVIDERS: tuple[str, ...] = get_args(GenAIProvider)


def now_ms() -> int:
    return int(time.time() * 1000)


# ---- crawl settings templates ----


async def create_template(
    db: AsyncSession, name: str, settings: dict, filters: dict | None
) -> CrawlSettingsTemplate:
    template = CrawlSettingsTemplate(
        id=str(uuid.uuid4()),
        name=name,
        settings=settings,
        filters=filters,
        created_at=now_ms(),
        updated_at=now_ms(),
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


async def list_templates(db: AsyncSession) -> list[CrawlSettingsTemplate]:
    result = await db.execute(
        select(CrawlSettingsTemplate).order_by(CrawlSettingsTemplate.name)
    )
    return list(result.scalars().all())


async def get_template(
    db: AsyncSession, template_id: str
) -> CrawlSettingsTemplate | None:
    return await db.get(CrawlSettingsTemplate, template_id)


async def update_template(
    db: AsyncSession,
    template: CrawlSettingsTemplate,
    name: str,
    settings: dict,
    filters: dict | None,
) -> CrawlSettingsTemplate:
    template.name = name
    template.settings = settings
    template.filters = filters
    template.updated_at = now_ms()
    await db.commit()
    await db.refresh(template)
    return template


async def delete_template(db: AsyncSession, template: CrawlSettingsTemplate) -> None:
    await db.delete(template)
    await db.commit()


# ---- provider API keys ----


async def list_api_keys(db: AsyncSession) -> dict[str, ProviderApiKey]:
    result = await db.execute(select(ProviderApiKey))
    return {row.provider: row for row in result.scalars().all()}


async def get_api_key_value(db: AsyncSession, provider: str) -> str | None:
    key = await db.get(ProviderApiKey, provider)
    return key.api_key if key else None


async def upsert_api_key(
    db: AsyncSession, provider: str, api_key: str
) -> ProviderApiKey:
    key = await db.get(ProviderApiKey, provider)
    if key is None:
        key = ProviderApiKey(provider=provider, api_key=api_key, updated_at=now_ms())
        db.add(key)
    else:
        key.api_key = api_key
        key.updated_at = now_ms()
    await db.commit()
    await db.refresh(key)
    return key


async def delete_api_key(db: AsyncSession, provider: str) -> None:
    key = await db.get(ProviderApiKey, provider)
    if key is not None:
        await db.delete(key)
        await db.commit()
