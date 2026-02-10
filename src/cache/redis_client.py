"""Redis connection management with connection pooling."""

from __future__ import annotations

import redis.asyncio as aioredis
import structlog

from src.config import RedisConfig

logger = structlog.get_logger(__name__)


_pool: aioredis.ConnectionPool | None = None


async def get_redis(config: RedisConfig | None = None) -> aioredis.Redis:
    """Get a Redis client from the connection pool."""
    global _pool
    if _pool is None:
        if config is None:
            from src.config import get_config
            config = get_config().redis
        _pool = aioredis.ConnectionPool.from_url(
            config.url,
            max_connections=20,
            decode_responses=True,
        )
        logger.info("redis_pool_created", url=f"{config.host}:{config.port}/{config.db}")
    return aioredis.Redis(connection_pool=_pool)


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
        logger.info("redis_pool_closed")
