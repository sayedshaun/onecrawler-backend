from typing import Optional

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from src.core.config import settings

_pool: Optional[ArqRedis] = None


async def get_arq_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    return _pool


async def close_arq_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
