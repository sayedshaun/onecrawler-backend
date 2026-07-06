from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dashboard import crud
from src.api.v1.dashboard.schema import DashboardOverviewOut, JobCountsOut, RecentJobOut
from src.db.pg import get_db

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/overview", response_model=DashboardOverviewOut)
async def get_overview(db: AsyncSession = Depends(get_db)):
    job_counts = await crud.count_jobs_by_status(db)
    url_counters = await crud.sum_url_counters(db)
    total = await crud.total_jobs(db)
    recent = await crud.recent_jobs(db, limit=10)

    return DashboardOverviewOut(
        total_jobs=total,
        job_counts=JobCountsOut(**job_counts),
        urls_discovered=url_counters["urls_discovered"],
        urls_scraped=url_counters["urls_scraped"],
        urls_failed=url_counters["urls_failed"],
        recent_jobs=[RecentJobOut.model_validate(job) for job in recent],
    )
