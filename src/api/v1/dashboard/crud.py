from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CrawlJob

_STATUSES = ("queued", "running", "completed", "failed", "cancelled")


async def total_jobs(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(CrawlJob))


async def count_jobs_by_status(db: AsyncSession) -> dict[str, int]:
    result = await db.execute(
        select(CrawlJob.status, func.count()).group_by(CrawlJob.status)
    )
    counts = {status: 0 for status in _STATUSES}
    for status, count in result.all():
        counts[status] = count
    return counts


async def sum_url_counters(db: AsyncSession) -> dict[str, int]:
    row = await db.execute(
        select(
            func.coalesce(func.sum(CrawlJob.urls_discovered), 0),
            func.coalesce(func.sum(CrawlJob.urls_scraped), 0),
            func.coalesce(func.sum(CrawlJob.urls_failed), 0),
        )
    )
    discovered, scraped, failed = row.one()
    return {
        "urls_discovered": int(discovered),
        "urls_scraped": int(scraped),
        "urls_failed": int(failed),
    }


async def recent_jobs(db: AsyncSession, limit: int = 10) -> list[CrawlJob]:
    result = await db.execute(
        select(CrawlJob).order_by(CrawlJob.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())
