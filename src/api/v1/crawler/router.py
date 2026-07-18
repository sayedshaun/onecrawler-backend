import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.security.dependencies import CurrentUser, get_current_user
from src.api.v1.crawler.schema import (
    CrawlJobDetailOut,
    CrawlJobSummaryOut,
    CrawlListOut,
    CreateCrawlRequest,
    DiscoveredListOut,
    LogListOut,
    ScrapeFromDiscoveredRequest,
)
from src.core.pool import get_arq_pool
from src.db.models import (
    CrawlJob,
    CrawlMode,
    CrawlResultItem,
    CrawlStatus,
    DiscoveredUrl,
    LogLine,
)
from src.db.pg import get_db

router = APIRouter(prefix="/crawls", tags=["Crawls"])

_ACTIVE_STATUSES = {CrawlStatus.QUEUED, CrawlStatus.RUNNING}


@router.post("", response_model=CrawlJobSummaryOut, status_code=status.HTTP_201_CREATED)
async def create_crawl(
    payload: CreateCrawlRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    job = CrawlJob(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        target_url=payload.target_url,
        mode=payload.mode,
        status=CrawlStatus.QUEUED,
        settings=payload.settings.model_dump(),
        filters=payload.filters.model_dump() if payload.filters else None,
        created_at=int(time.time() * 1000),
        url_limit=payload.settings.link_extraction_limit,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    pool = await get_arq_pool()
    await pool.enqueue_job("run_crawl_job", job.id, _job_id=job.id)

    return job


@router.get("", response_model=CrawlListOut)
async def list_crawls(
    status: str | None = None,
    q: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    query = select(CrawlJob).where(CrawlJob.user_id == current_user.id)
    count_query = (
        select(func.count())
        .select_from(CrawlJob)
        .where(CrawlJob.user_id == current_user.id)
    )
    if status:
        query = query.where(CrawlJob.status == status)
        count_query = count_query.where(CrawlJob.status == status)
    if q:
        query = query.where(CrawlJob.target_url.ilike(f"%{q}%"))
        count_query = count_query.where(CrawlJob.target_url.ilike(f"%{q}%"))

    total = await db.scalar(count_query)
    result = await db.execute(
        query.order_by(CrawlJob.created_at.desc()).limit(limit).offset(offset)
    )
    items = list(result.scalars().all())
    return CrawlListOut(items=items, total=total, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=CrawlJobDetailOut)
async def get_crawl(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    job = await db.scalar(
        select(CrawlJob).where(
            CrawlJob.id == job_id, CrawlJob.user_id == current_user.id
        )
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Crawl job not found"
        )

    result = await db.execute(
        select(CrawlResultItem.extracted_at).where(CrawlResultItem.job_id == job_id)
    )
    buckets: dict[int, int] = {}
    for (extracted_at,) in result.all():
        second = extracted_at // 1000
        buckets[second] = buckets.get(second, 0) + 1
    throughput_history = [
        {"t": second * 1000, "pages_per_sec": float(count)}
        for second, count in sorted(buckets.items())
    ]

    discovered_result = await db.execute(
        select(DiscoveredUrl.discovered_at).where(DiscoveredUrl.job_id == job_id)
    )
    discovery_buckets: dict[int, int] = {}
    for (discovered_at,) in discovered_result.all():
        second = discovered_at // 1000
        discovery_buckets[second] = discovery_buckets.get(second, 0) + 1
    discovery_history = []
    cumulative = 0
    for second, count in sorted(discovery_buckets.items()):
        cumulative += count
        discovery_history.append({"t": second * 1000, "count": cumulative})

    return CrawlJobDetailOut.model_validate(
        {
            **{name: getattr(job, name) for name in CrawlJobSummaryOut.model_fields},
            "settings": job.settings,
            "throughput_history": throughput_history,
            "discovery_history": discovery_history,
        }
    )


@router.get("/{job_id}/download")
async def download_crawl_results(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    job = await db.scalar(
        select(CrawlJob).where(
            CrawlJob.id == job_id, CrawlJob.user_id == current_user.id
        )
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Crawl job not found"
        )

    result = await db.execute(
        select(CrawlResultItem)
        .where(CrawlResultItem.job_id == job_id)
        .order_by(CrawlResultItem.extracted_at)
    )
    items = [
        {
            "id": item.id,
            "url": item.url,
            "title": item.title,
            "word_count": item.word_count,
            "format": item.format,
            "extracted_at": item.extracted_at,
            "content": item.content,
        }
        for item in result.scalars().all()
    ]

    return Response(
        content=json.dumps(items, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{job_id}.json"'},
    )


@router.get("/{job_id}/logs", response_model=LogListOut)
async def get_crawl_logs(
    job_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    job = await db.scalar(
        select(CrawlJob).where(
            CrawlJob.id == job_id, CrawlJob.user_id == current_user.id
        )
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Crawl job not found"
        )

    total = await db.scalar(
        select(func.count()).select_from(LogLine).where(LogLine.job_id == job_id)
    )
    result = await db.execute(
        select(LogLine)
        .where(LogLine.job_id == job_id)
        .order_by(LogLine.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list(result.scalars().all())
    return LogListOut(items=items, total=total, limit=limit, offset=offset)


@router.get("/{job_id}/discovered", response_model=DiscoveredListOut)
async def list_discovered_urls(
    job_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    job = await db.scalar(
        select(CrawlJob).where(
            CrawlJob.id == job_id, CrawlJob.user_id == current_user.id
        )
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Crawl job not found"
        )

    total = await db.scalar(
        select(func.count())
        .select_from(DiscoveredUrl)
        .where(DiscoveredUrl.job_id == job_id)
    )
    result = await db.execute(
        select(DiscoveredUrl)
        .where(DiscoveredUrl.job_id == job_id)
        .order_by(DiscoveredUrl.discovered_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list(result.scalars().all())
    return DiscoveredListOut(items=items, total=total, limit=limit, offset=offset)


@router.delete(
    "/{job_id}/discovered/{discovered_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_discovered_url(
    job_id: str,
    discovered_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    job = await db.scalar(
        select(CrawlJob).where(
            CrawlJob.id == job_id, CrawlJob.user_id == current_user.id
        )
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Crawl job not found"
        )

    row = await db.scalar(
        select(DiscoveredUrl).where(
            DiscoveredUrl.id == discovered_id, DiscoveredUrl.job_id == job_id
        )
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Discovered URL not found"
        )

    await db.delete(row)
    await db.commit()


@router.post(
    "/{job_id}/scrape",
    response_model=CrawlJobSummaryOut,
    status_code=status.HTTP_201_CREATED,
)
async def scrape_discovered_urls(
    job_id: str,
    payload: ScrapeFromDiscoveredRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    source_job = await db.scalar(
        select(CrawlJob).where(
            CrawlJob.id == job_id, CrawlJob.user_id == current_user.id
        )
    )
    if source_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Crawl job not found"
        )

    discovered = await db.execute(
        select(DiscoveredUrl.url)
        .where(DiscoveredUrl.job_id == job_id)
        .order_by(DiscoveredUrl.discovered_at)
    )
    urls = list(dict.fromkeys(url for (url,) in discovered.all()))
    if not urls:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No discovered URLs available to scrape",
        )

    job = CrawlJob(
        id=str(uuid.uuid4()),
        user_id=source_job.user_id,
        target_url=source_job.target_url,
        mode=CrawlMode.SCRAPER,
        status=CrawlStatus.QUEUED,
        settings=payload.settings.model_dump(),
        filters=None,
        seed_urls=urls,
        created_at=int(time.time() * 1000),
        url_limit=len(urls),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    pool = await get_arq_pool()
    await pool.enqueue_job("run_crawl_job", job.id, _job_id=job.id)

    return job


@router.post("/{job_id}/cancel", response_model=CrawlJobSummaryOut)
async def cancel_crawl(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    job = await db.scalar(
        select(CrawlJob).where(
            CrawlJob.id == job_id, CrawlJob.user_id == current_user.id
        )
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Crawl job not found"
        )

    if job.status in _ACTIVE_STATUSES:
        job.status = CrawlStatus.CANCELLED
        job.finished_at = int(time.time() * 1000)
        await db.commit()
        await db.refresh(job)

    return job


@router.post(
    "/{job_id}/retry",
    response_model=CrawlJobSummaryOut,
    status_code=status.HTTP_201_CREATED,
)
async def retry_crawl(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    source_job = await db.scalar(
        select(CrawlJob).where(
            CrawlJob.id == job_id, CrawlJob.user_id == current_user.id
        )
    )
    if source_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Crawl job not found"
        )
    if source_job.status not in (CrawlStatus.FAILED, CrawlStatus.CANCELLED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed or cancelled crawl jobs can be retried",
        )

    job = CrawlJob(
        id=str(uuid.uuid4()),
        user_id=source_job.user_id,
        target_url=source_job.target_url,
        mode=source_job.mode,
        status=CrawlStatus.QUEUED,
        settings=source_job.settings,
        filters=source_job.filters,
        seed_urls=source_job.seed_urls,
        created_at=int(time.time() * 1000),
        url_limit=source_job.url_limit,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    pool = await get_arq_pool()
    await pool.enqueue_job("run_crawl_job", job.id, _job_id=job.id)

    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_crawl(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    job = await db.scalar(
        select(CrawlJob).where(
            CrawlJob.id == job_id, CrawlJob.user_id == current_user.id
        )
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Crawl job not found"
        )
    if job.status in _ACTIVE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cancel the crawl before deleting it",
        )

    await db.delete(job)
    await db.commit()
