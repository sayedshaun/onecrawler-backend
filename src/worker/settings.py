from arq.connections import RedisSettings

from src.core.config import settings as app_settings
from src.worker.tasks import run_crawl_job


async def shutdown(ctx) -> None:
    from src.db.pg import engine

    await engine.dispose()


class WorkerSettings:
    functions = [run_crawl_job]
    redis_settings = RedisSettings.from_dsn(app_settings.REDIS_URL)
    on_shutdown = shutdown
    max_jobs = 4
    job_timeout = 3600
