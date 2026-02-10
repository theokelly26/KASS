"""Consumes orderbook deltas/snapshots from Redis and writes to TimescaleDB.

Also periodically takes snapshots from Redis state and persists them.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

import orjson
import structlog

from src.cache.redis_client import get_redis
from src.cache.state import OrderbookStateManager
from src.cache.streams import (
    STREAM_ORDERBOOK_DELTAS,
    STREAM_ORDERBOOK_SNAPSHOTS,
    RedisStreamConsumer,
)
from src.config import AppConfig, get_config
from src.models import OrderbookDelta, OrderbookSnapshot
from src.persistence.db import get_connection

logger = structlog.get_logger(__name__)

CONSUMER_GROUP = "db_writers"
CONSUMER_NAME_DELTA = "ob_writer_delta_1"
CONSUMER_NAME_SNAP = "ob_writer_snap_1"


class OrderbookWriter:
    """
    Consumes orderbook data from Redis streams and writes to TimescaleDB.

    - Deltas are written to orderbook_deltas table
    - Periodic snapshots from Redis state are written to orderbook_snapshots
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._total_deltas = 0
        self._total_snapshots = 0

    async def run(self) -> None:
        """Main consumer loop — runs delta consumer and snapshot loop concurrently."""
        redis = await get_redis(self._config.redis)
        consumer = RedisStreamConsumer(redis)
        state_mgr = OrderbookStateManager(redis)

        tasks = [
            asyncio.create_task(self._consume_deltas(consumer)),
            asyncio.create_task(self._consume_snapshots(consumer)),
            asyncio.create_task(self._periodic_snapshot(state_mgr)),
        ]

        logger.info("orderbook_writer_started")
        await asyncio.gather(*tasks)

    async def _consume_deltas(self, consumer: RedisStreamConsumer) -> None:
        """Consume orderbook deltas and write to DB."""
        await consumer.consume(
            stream=STREAM_ORDERBOOK_DELTAS,
            group=CONSUMER_GROUP,
            consumer=CONSUMER_NAME_DELTA,
            handler=self._handle_delta_batch,
            batch_size=200,
        )

    async def _consume_snapshots(self, consumer: RedisStreamConsumer) -> None:
        """Consume orderbook snapshots from the stream."""
        await consumer.consume(
            stream=STREAM_ORDERBOOK_SNAPSHOTS,
            group=CONSUMER_GROUP,
            consumer=CONSUMER_NAME_SNAP,
            handler=self._handle_snapshot_batch,
            batch_size=50,
        )

    async def _handle_delta_batch(self, messages: list[dict[str, Any]]) -> None:
        """Write orderbook deltas to DB."""
        deltas = []
        for msg in messages:
            try:
                data = orjson.loads(msg.get("data", "{}"))
                delta = OrderbookDelta.model_validate(data)
                deltas.append(delta)
            except Exception:
                logger.exception("ob_delta_parse_skip", msg_id=msg.get("id"))

        if not deltas:
            return

        retries = 0
        while retries < 3:
            try:
                async with get_connection(self._config.postgres) as conn:
                    async with conn.cursor() as cur:
                        for d in deltas:
                            row = d.to_db_row()
                            await cur.execute(
                                """
                                INSERT INTO orderbook_deltas (ts, market_ticker, price,
                                    delta, side, is_own_order)
                                VALUES (%(ts)s, %(market_ticker)s, %(price)s,
                                        %(delta)s, %(side)s, %(is_own_order)s)
                                """,
                                row,
                            )
                    await conn.commit()

                self._total_deltas += len(deltas)
                logger.debug("ob_deltas_flushed", count=len(deltas))
                return

            except Exception:
                retries += 1
                logger.exception("ob_delta_flush_error", retry=retries)
                await asyncio.sleep(2 ** retries)

    async def _handle_snapshot_batch(self, messages: list[dict[str, Any]]) -> None:
        """Write orderbook snapshots from stream to DB."""
        for msg in messages:
            try:
                data = orjson.loads(msg.get("data", "{}"))
                snapshot = OrderbookSnapshot.model_validate(data)
                await self._write_snapshot(snapshot)
            except Exception:
                logger.exception("ob_snapshot_parse_skip", msg_id=msg.get("id"))

    async def _write_snapshot(self, snapshot: OrderbookSnapshot) -> None:
        """Write a single snapshot to the database."""
        row = snapshot.to_db_row()
        async with get_connection(self._config.postgres) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO orderbook_snapshots (ts, market_ticker, yes_levels,
                        no_levels, spread, yes_depth_5, no_depth_5)
                    VALUES (%(ts)s, %(market_ticker)s, %(yes_levels)s,
                            %(no_levels)s, %(spread)s, %(yes_depth_5)s, %(no_depth_5)s)
                    """,
                    row,
                )
            await conn.commit()
        self._total_snapshots += 1

    async def _periodic_snapshot(self, state_mgr: OrderbookStateManager) -> None:
        """Periodically snapshot the current orderbook state from Redis."""
        interval = self._config.tuning.orderbook_snapshot_interval

        while True:
            await asyncio.sleep(interval)

            try:
                # Get list of active markets with orderbooks in Redis
                redis = await get_redis(self._config.redis)
                keys = []
                async for key in redis.scan_iter(match="state:orderbook:*"):
                    keys.append(key)

                for key in keys:
                    ticker = key.split(":")[-1]
                    book = await state_mgr.get_current_book(ticker)
                    if book is None:
                        continue

                    # Reconstruct as snapshot for DB
                    yes_levels = [
                        [int(p), q] for p, q in book.get("yes", {}).items()
                    ]
                    no_levels = [
                        [int(p), q] for p, q in book.get("no", {}).items()
                    ]

                    row = {
                        "ts": datetime.now(tz=timezone.utc),
                        "market_ticker": ticker,
                        "yes_levels": orjson.dumps(yes_levels).decode(),
                        "no_levels": orjson.dumps(no_levels).decode(),
                        "spread": await state_mgr.get_spread(ticker),
                        "yes_depth_5": sum(
                            q for _, q in sorted(yes_levels, key=lambda x: -x[0])[:5]
                        ),
                        "no_depth_5": sum(
                            q for _, q in sorted(no_levels, key=lambda x: -x[0])[:5]
                        ),
                    }

                    async with get_connection(self._config.postgres) as conn:
                        async with conn.cursor() as cur:
                            await cur.execute(
                                """
                                INSERT INTO orderbook_snapshots (ts, market_ticker,
                                    yes_levels, no_levels, spread, yes_depth_5, no_depth_5)
                                VALUES (%(ts)s, %(market_ticker)s, %(yes_levels)s,
                                        %(no_levels)s, %(spread)s, %(yes_depth_5)s,
                                        %(no_depth_5)s)
                                """,
                                row,
                            )
                        await conn.commit()

                logger.info("periodic_snapshots_taken", count=len(keys))

            except Exception:
                logger.exception("periodic_snapshot_error")


async def main() -> None:
    import structlog

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
    )

    config = get_config()
    writer = OrderbookWriter(config)
    await writer.run()


if __name__ == "__main__":
    asyncio.run(main())
