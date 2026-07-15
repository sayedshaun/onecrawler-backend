import io
import json
import zipfile

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.security.dependencies import CurrentUser, get_current_user
from src.api.v1.data.schema import (
    DataExportRequest,
    DataItemDetailOut,
    DataItemOut,
    DataListOut,
    ExportArchiveFormat,
)
from src.db.models import CrawlJob, CrawlResultItem
from src.db.pg import get_db

router = APIRouter(prefix="/data", tags=["Data"])


@router.get("", response_model=DataListOut)
async def list_data(
    job_id: str | None = None,
    format: str | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    count_query = (
        select(func.count())
        .select_from(CrawlResultItem)
        .join(CrawlJob, CrawlJob.id == CrawlResultItem.job_id)
        .where(CrawlJob.user_id == current_user.id)
    )
    query = (
        select(CrawlResultItem, CrawlJob.target_url)
        .join(CrawlJob, CrawlJob.id == CrawlResultItem.job_id)
        .where(CrawlJob.user_id == current_user.id)
    )
    if job_id:
        count_query = count_query.where(CrawlResultItem.job_id == job_id)
        query = query.where(CrawlResultItem.job_id == job_id)
    if format:
        count_query = count_query.where(CrawlResultItem.format == format)
        query = query.where(CrawlResultItem.format == format)
    if q:
        like = f"%{q}%"
        search_clause = (
            CrawlResultItem.title.ilike(like)
            | CrawlResultItem.url.ilike(like)
            | CrawlResultItem.preview.ilike(like)
        )
        count_query = count_query.where(search_clause)
        query = query.where(search_clause)

    total = await db.scalar(count_query)
    rows = await db.execute(
        query.order_by(CrawlResultItem.extracted_at.desc()).limit(limit).offset(offset)
    )

    items = [
        DataItemOut(
            id=item.id,
            job_id=item.job_id,
            target_url=target_url,
            url=item.url,
            title=item.title,
            word_count=item.word_count,
            format=item.format,
            extracted_at=item.extracted_at,
            preview=item.preview,
        )
        for item, target_url in rows.all()
    ]

    return DataListOut(items=items, total=total, limit=limit, offset=offset)


@router.post("/export")
async def export_data(
    payload: DataExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    query = (
        select(CrawlResultItem, CrawlJob.target_url)
        .join(CrawlJob, CrawlJob.id == CrawlResultItem.job_id)
        .where(CrawlJob.user_id == current_user.id)
    )
    if payload.ids:
        query = query.where(CrawlResultItem.id.in_(payload.ids))
    else:
        if payload.job_id:
            query = query.where(CrawlResultItem.job_id == payload.job_id)
        if payload.format:
            query = query.where(CrawlResultItem.format == payload.format)
        if payload.q:
            like = f"%{payload.q}%"
            query = query.where(
                CrawlResultItem.title.ilike(like)
                | CrawlResultItem.url.ilike(like)
                | CrawlResultItem.preview.ilike(like)
            )

    rows = await db.execute(query.order_by(CrawlResultItem.extracted_at.desc()))
    results = rows.all()
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No matching results found"
        )

    items = [
        DataItemDetailOut(
            id=item.id,
            job_id=item.job_id,
            target_url=target_url,
            url=item.url,
            title=item.title,
            word_count=item.word_count,
            format=item.format,
            extracted_at=item.extracted_at,
            preview=item.preview,
            content=item.content,
        )
        for item, target_url in results
    ]

    if payload.archive_format == ExportArchiveFormat.ndjson:
        body = "\n".join(
            json.dumps(item.model_dump(mode="json", by_alias=True), ensure_ascii=False)
            for item in items
        )
        return Response(
            content=body,
            media_type="application/x-ndjson",
            headers={"Content-Disposition": 'attachment; filename="export.ndjson"'},
        )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in items:
            archive.writestr(
                f"{item.id}.json",
                json.dumps(
                    item.model_dump(mode="json", by_alias=True),
                    ensure_ascii=False,
                    indent=2,
                ),
            )

    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="export.zip"'},
    )


@router.get("/{result_id}", response_model=DataItemDetailOut)
async def get_data_item(
    result_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    row = await db.execute(
        select(CrawlResultItem, CrawlJob.target_url)
        .join(CrawlJob, CrawlJob.id == CrawlResultItem.job_id)
        .where(CrawlResultItem.id == result_id, CrawlJob.user_id == current_user.id)
    )
    found = row.first()
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Result not found"
        )

    item, target_url = found

    return DataItemDetailOut(
        id=item.id,
        job_id=item.job_id,
        target_url=target_url,
        url=item.url,
        title=item.title,
        word_count=item.word_count,
        format=item.format,
        extracted_at=item.extracted_at,
        preview=item.preview,
        content=item.content,
    )


@router.get("/{result_id}/download")
async def download_data_item(
    result_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    row = await db.execute(
        select(CrawlResultItem)
        .join(CrawlJob, CrawlJob.id == CrawlResultItem.job_id)
        .where(CrawlResultItem.id == result_id, CrawlJob.user_id == current_user.id)
    )
    item = row.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Result not found")

    return Response(
        content=json.dumps(item.content, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{item.id}.json"'},
    )
