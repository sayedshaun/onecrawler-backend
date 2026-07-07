from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CrawlJob, CrawlResultItem


def _apply_filters(query, job_id: str | None, format: str | None, search: str | None):
    if job_id:
        query = query.where(CrawlResultItem.job_id == job_id)
    if format:
        query = query.where(CrawlResultItem.format == format)
    if search:
        like = f"%{search}%"
        query = query.where(
            CrawlResultItem.title.ilike(like)
            | CrawlResultItem.url.ilike(like)
            | CrawlResultItem.preview.ilike(like)
        )
    return query


async def list_results(
    db: AsyncSession,
    *,
    job_id: str | None = None,
    format: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[CrawlResultItem, str]], int]:
    count_query = _apply_filters(
        select(func.count()).select_from(CrawlResultItem), job_id, format, search
    )
    total = await db.scalar(count_query)

    query = _apply_filters(
        select(CrawlResultItem, CrawlJob.target_url).join(
            CrawlJob, CrawlJob.id == CrawlResultItem.job_id
        ),
        job_id,
        format,
        search,
    )
    rows = await db.execute(
        query.order_by(CrawlResultItem.extracted_at.desc()).limit(limit).offset(offset)
    )
    return list(rows.all()), total


async def get_result(
    db: AsyncSession, result_id: str
) -> tuple[CrawlResultItem, str] | None:
    row = await db.execute(
        select(CrawlResultItem, CrawlJob.target_url)
        .join(CrawlJob, CrawlJob.id == CrawlResultItem.job_id)
        .where(CrawlResultItem.id == result_id)
    )
    return row.first()
