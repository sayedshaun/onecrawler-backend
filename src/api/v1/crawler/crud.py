import time
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CrawlJob, CrawlResultItem, DiscoveredUrl, LogLine


def now_ms() -> int:
    return int(time.time() * 1000)


async def create_job(
    db: AsyncSession,
    target_url: str,
    mode: str,
    settings: dict,
    filters: dict | None,
    url_limit: int,
) -> CrawlJob:
    job = CrawlJob(
        id=str(uuid.uuid4()),
        target_url=target_url,
        mode=mode,
        status="queued",
        settings=settings,
        filters=filters,
        created_at=now_ms(),
        url_limit=url_limit,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def get_job(db: AsyncSession, job_id: str) -> CrawlJob | None:
    result = await db.execute(select(CrawlJob).where(CrawlJob.id == job_id))
    return result.scalar_one_or_none()


def _apply_job_filters(query, status: str | None, search: str | None):
    if status:
        query = query.where(CrawlJob.status == status)
    if search:
        query = query.where(CrawlJob.target_url.ilike(f"%{search}%"))
    return query


async def count_jobs(
    db: AsyncSession, status: str | None = None, search: str | None = None
) -> int:
    query = _apply_job_filters(
        select(func.count()).select_from(CrawlJob), status, search
    )
    return await db.scalar(query)


async def list_jobs(
    db: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    status: str | None = None,
    search: str | None = None,
) -> list[CrawlJob]:
    query = _apply_job_filters(select(CrawlJob), status, search)
    result = await db.execute(
        query.order_by(CrawlJob.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


async def cancel_job(db: AsyncSession, job: CrawlJob) -> CrawlJob:
    if job.status in ("queued", "running"):
        job.status = "cancelled"
        job.finished_at = now_ms()
        await db.commit()
        await db.refresh(job)
    return job


async def delete_job(db: AsyncSession, job: CrawlJob) -> None:
    await db.delete(job)
    await db.commit()


async def list_discovered_urls_all(db: AsyncSession, job_id: str) -> list[str]:
    """Distinct URLs still discovered on the job, in discovery order."""
    result = await db.execute(
        select(DiscoveredUrl.url)
        .where(DiscoveredUrl.job_id == job_id)
        .order_by(DiscoveredUrl.discovered_at)
    )
    return list(dict.fromkeys(row[0] for row in result.all()))


async def create_scrape_job(
    db: AsyncSession, source_job: CrawlJob, settings: dict
) -> CrawlJob | None:
    urls = await list_discovered_urls_all(db, source_job.id)
    if not urls:
        return None

    job = CrawlJob(
        id=str(uuid.uuid4()),
        target_url=source_job.target_url,
        mode="scraper",
        status="queued",
        settings=settings,
        filters=None,
        seed_urls=urls,
        created_at=now_ms(),
        url_limit=len(urls),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def delete_discovered(db: AsyncSession, job_id: str, discovered_id: str) -> bool:
    result = await db.execute(
        select(DiscoveredUrl).where(
            DiscoveredUrl.id == discovered_id, DiscoveredUrl.job_id == job_id
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return False

    await db.delete(row)
    await db.commit()
    return True


async def count_discovered(db: AsyncSession, job_id: str) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(DiscoveredUrl)
        .where(DiscoveredUrl.job_id == job_id)
    )


async def list_discovered(
    db: AsyncSession, job_id: str, limit: int = 50, offset: int = 0
) -> list[DiscoveredUrl]:
    result = await db.execute(
        select(DiscoveredUrl)
        .where(DiscoveredUrl.job_id == job_id)
        .order_by(DiscoveredUrl.discovered_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def count_logs(db: AsyncSession, job_id: str) -> int:
    return await db.scalar(
        select(func.count()).select_from(LogLine).where(LogLine.job_id == job_id)
    )


async def list_logs(
    db: AsyncSession, job_id: str, limit: int = 50, offset: int = 0
) -> list[LogLine]:
    result = await db.execute(
        select(LogLine)
        .where(LogLine.job_id == job_id)
        .order_by(LogLine.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def throughput_history(db: AsyncSession, job_id: str) -> list[dict]:
    """Buckets result extraction timestamps into per-second pages/sec samples."""
    result = await db.execute(
        select(CrawlResultItem.extracted_at).where(CrawlResultItem.job_id == job_id)
    )
    timestamps = [row[0] for row in result.all()]
    if not timestamps:
        return []

    buckets: dict[int, int] = {}
    for extracted_at in timestamps:
        second = extracted_at // 1000
        buckets[second] = buckets.get(second, 0) + 1

    return [
        {"t": second * 1000, "pages_per_sec": float(count)}
        for second, count in sorted(buckets.items())
    ]
