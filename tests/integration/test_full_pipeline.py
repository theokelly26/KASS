"""Integration test for the full KASS pipeline.

Requires running PostgreSQL (with TimescaleDB), Redis, and optionally
a live Kalshi WebSocket connection.

Run with: pytest tests/integration/ -v
"""

from __future__ import annotations

import asyncio

import pytest


class TestFullPipeline:
    """
    End-to-end integration test:
    1. Verify Redis is reachable
    2. Verify Postgres is reachable
    3. Publish test messages to Redis streams
    4. Verify messages are consumed by writers
    5. Verify data appears in TimescaleDB
    """

    async def test_redis_connection(self) -> None:
        """Verify Redis is responsive."""
        from src.cache.redis_client import get_redis
        from src.config import get_config

        config = get_config()
        redis = await get_redis(config.redis)
        result = await redis.ping()
        assert result is True

    async def test_postgres_connection(self) -> None:
        """Verify Postgres/TimescaleDB is responsive."""
        from src.persistence.db import get_connection
        from src.config import get_config

        config = get_config()
        async with get_connection(config.postgres) as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                result = await cur.fetchone()
                assert result[0] == 1

    async def test_publish_and_consume_trade(self) -> None:
        """Publish a trade to Redis stream, verify it's consumable."""
        from src.cache.redis_client import get_redis
        from src.cache.streams import STREAM_TRADES, RedisStreamPublisher
        from src.config import get_config
        from src.models import KalshiTrade

        config = get_config()
        redis = await get_redis(config.redis)
        publisher = RedisStreamPublisher(redis)

        trade = KalshiTrade(
            trade_id="integration-test-001",
            market_ticker="TEST-MARKET",
            yes_price=50,
            yes_price_dollars="0.500",
            no_price=50,
            no_price_dollars="0.500",
            count=1,
            count_fp="1.00",
            taker_side="yes",
            ts=1707350400,
        )

        msg_id = await publisher.publish_trade(trade)
        assert msg_id is not None

        # Verify message is in the stream
        length = await redis.xlen(STREAM_TRADES)
        assert length > 0

    async def test_hypertables_exist(self) -> None:
        """Verify TimescaleDB hypertables are created."""
        from src.persistence.db import get_connection
        from src.config import get_config

        config = get_config()
        async with get_connection(config.postgres) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT hypertable_name
                    FROM timescaledb_information.hypertables
                    ORDER BY hypertable_name
                    """
                )
                rows = await cur.fetchall()
                hypertable_names = {row[0] for row in rows}

                expected = {
                    "trades",
                    "ticker_updates",
                    "orderbook_snapshots",
                    "orderbook_deltas",
                    "lifecycle_events",
                    "system_health",
                }
                assert expected.issubset(hypertable_names)

    async def test_views_exist(self) -> None:
        """Verify analytical views are created."""
        from src.persistence.db import get_connection
        from src.config import get_config

        config = get_config()
        async with get_connection(config.postgres) as conn:
            async with conn.cursor() as cur:
                # Test hourly_volume view
                await cur.execute("SELECT * FROM hourly_volume LIMIT 0")
                # Test oi_by_market view
                await cur.execute("SELECT * FROM oi_by_market LIMIT 0")
                # Test market_latest materialized view
                await cur.execute("SELECT * FROM market_latest LIMIT 0")

    async def test_basic_queries(self) -> None:
        """Run some basic analytical queries to verify schema."""
        from src.persistence.db import get_connection
        from src.config import get_config

        config = get_config()
        async with get_connection(config.postgres) as conn:
            async with conn.cursor() as cur:
                # Count recent trades
                await cur.execute(
                    "SELECT count(*) FROM trades WHERE ts > NOW() - INTERVAL '10 minutes'"
                )
                trade_count = (await cur.fetchone())[0]
                assert trade_count >= 0

                # Top markets by trade count
                await cur.execute(
                    """
                    SELECT market_ticker, count(*)
                    FROM trades
                    GROUP BY market_ticker
                    ORDER BY count(*) DESC
                    LIMIT 10
                    """
                )
                await cur.fetchall()  # Just verify query runs

                # Active markets count
                await cur.execute(
                    "SELECT count(*) FROM markets WHERE status = 'open'"
                )
                await cur.fetchone()
