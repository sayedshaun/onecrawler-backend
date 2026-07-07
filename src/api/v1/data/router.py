from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.data import crud
from src.api.v1.data.schema import DataItemDetailOut, DataItemOut, DataListOut
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
):
    rows, total = await crud.list_results(
        db, job_id=job_id, format=format, search=q, limit=limit, offset=offset
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
        for item, target_url in rows
    ]

    return DataListOut(items=items, total=total, limit=limit, offset=offset)


@router.get("/{result_id}", response_model=DataItemDetailOut)
async def get_data_item(result_id: str, db: AsyncSession = Depends(get_db)):
    row = await crud.get_result(db, result_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Result not found")

    item, target_url = row

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
