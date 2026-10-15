from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis

from app.core.config import settings

# One client per process. It owns a connection pool and connects lazily, so
# importing this module does not require Redis to be up.
redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


async def get_redis() -> Redis:
    return redis_client


RedisClient = Annotated[Redis, Depends(get_redis)]
