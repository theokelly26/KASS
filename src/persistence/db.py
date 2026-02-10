"""TimescaleDB connection pool management using psycopg3."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import psycopg
import psycopg_pool
import structlog

from src.config import PostgresConfig

logger = structlog.get_logger(__name__)

_pool: psycopg_pool.AsyncConnectionPool | None = None


async def get_pool(config: PostgresConfig | None = None) -> psycopg_pool.AsyncConnectionPool:
    """Get or create the async connection pool."""
    global _pool
    if _pool is None:
        if config is None:
            from src.config import get_config
            config = get_config().postgres
        _pool = psycopg_pool.AsyncConnectionPool(
            conninfo=config.dsn,
            min_size=config.pool_min,
            max_size=config.pool_max,
            open=False,
        )
        await _pool.open()
        logger.info(
            "db_pool_created",
            host=config.host,
            port=config.port,
            db=config.db,
            pool_min=config.pool_min,
            pool_max=config.pool_max,
        )
    return _pool


async def close_pool() -> None:
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("db_pool_closed")


@asynccontextmanager
async def get_connection(
    config: PostgresConfig | None = None,
) -> AsyncIterator[psycopg.AsyncConnection]:
    """Get a connection from the pool as an async context manager."""
    pool = await get_pool(config)
    async with pool.connection() as conn:
        yield conn


@asynccontextmanager
async def get_cursor(
    config: PostgresConfig | None = None,
) -> AsyncIterator[psycopg.AsyncCursor]:
    """Get a cursor from the pool as an async context manager."""
    async with get_connection(config) as conn:
        async with conn.cursor() as cur:
            yield cur
