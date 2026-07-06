from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.crawler import crud
from src.api.v1.crawler.schema import (
    CrawlJobDetailOut,
    CrawlJobSummaryOut,
    CrawlListOut,
    CreateCrawlRequest,
    DiscoveredListOut,
    LogListOut,
)
from src.core.pool import get_arq_pool
from src.db.pg import get_db

router = APIRouter(prefix="/crawls", tags=["Crawls"])

_ACTIVE_STATUSES = {"queued", "running"}


@router.post("", response_model=CrawlJobSummaryOut, status_code=status.HTTP_201_CREATED)
async def create_crawl(payload: CreateCrawlRequest, db: AsyncSession = Depends(get_db)):
    job = await crud.create_job(
        db,
        target_url=payload.target_url,
        mode=payload.mode,
        settings=payload.settings.model_dump(),
        filters=payload.filters.model_dump() if payload.filters else None,
        url_limit=payload.settings.link_extraction_limit,
    )

    pool = await get_arq_pool()
    await pool.enqueue_job("run_crawl_job", job.id, _job_id=job.id)

    return job


@router.get("", response_model=CrawlListOut)
async def list_crawls(
    status: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    items = await crud.list_jobs(db, limit=limit, offset=offset, status=status, search=q)
    total = await crud.count_jobs(db, status=status, search=q)
    return CrawlListOut(items=items, total=total, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=CrawlJobDetailOut)
async def get_crawl(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await crud.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crawl job not found")

    return CrawlJobDetailOut.model_validate(
        {
            **{name: getattr(job, name) for name in CrawlJobSummaryOut.model_fields},
            "settings": job.settings,
            "throughput_history": await crud.throughput_history(db, job_id),
        }
    )


@router.get("/{job_id}/logs", response_model=LogListOut)
async def get_crawl_logs(
    job_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    job = await crud.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crawl job not found")

    items = await crud.list_logs(db, job_id, limit=limit, offset=offset)
    total = await crud.count_logs(db, job_id)
    return LogListOut(items=items, total=total, limit=limit, offset=offset)


@router.get("/{job_id}/discovered", response_model=DiscoveredListOut)
async def list_discovered_urls(
    job_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    job = await crud.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crawl job not found")

    items = await crud.list_discovered(db, job_id, limit=limit, offset=offset)
    total = await crud.count_discovered(db, job_id)
    return DiscoveredListOut(items=items, total=total, limit=limit, offset=offset)


@router.post("/{job_id}/cancel", response_model=CrawlJobSummaryOut)
async def cancel_crawl(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await crud.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crawl job not found")

    return await crud.cancel_job(db, job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_crawl(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await crud.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crawl job not found")
    if job.status in _ACTIVE_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cancel the crawl before deleting it")

    await crud.delete_job(db, job)
