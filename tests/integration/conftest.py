"""Conftest for integration tests — resets global connection pools between tests."""

from __future__ import annotations

import pytest

import src.cache.redis_client as redis_mod
import src.persistence.db as db_mod


@pytest.fixture(autouse=True)
async def reset_connection_pools():
    """Reset global Redis and Postgres pools before each test.

    Each async test gets its own event loop, so connection pools
    from a previous test's loop will be stale.
    """
    # Reset before test
    redis_mod._pool = None
    db_mod._pool = None

    yield

    # Cleanup after test
    if redis_mod._pool is not None:
        await redis_mod._pool.aclose()
        redis_mod._pool = None
    if db_mod._pool is not None:
        await db_mod._pool.close()
        db_mod._pool = None
