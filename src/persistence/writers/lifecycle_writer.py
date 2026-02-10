"""Consumes market lifecycle events from Redis stream and writes to TimescaleDB."""

from __future__ import annotations

import asyncio
from typing import Any

import orjson
import structlog

from src.cache.redis_client import get_redis
from src.cache.streams import STREAM_LIFECYCLE, RedisStreamConsumer
from src.config import AppConfig, get_config
from src.models import MarketLifecycleEvent
from src.persistence.db import get_connection

logger = structlog.get_logger(__name__)

CONSUMER_GROUP = "db_writers"
CONSUMER_NAME = "lifecycle_writer_1"


class LifecycleWriter:
    """
    Consumes from kalshi:lifecycle Redis stream.
    Writes to lifecycle_events hypertable.
    Also updates the markets table status on lifecycle changes.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._total_written = 0

    async def run(self) -> None:
        """Main consumer loop."""
        redis = await get_redis(self._config.redis)
        consumer = RedisStreamConsumer(redis)

        logger.info("lifecycle_writer_started")

        await consumer.consume(
            stream=STREAM_LIFECYCLE,
            group=CONSUMER_GROUP,
            consumer=CONSUMER_NAME,
            handler=self._handle_batch,
            batch_size=50,
        )

    async def _handle_batch(self, messages: list[dict[str, Any]]) -> None:
        """Process lifecycle events."""
        events = []
        for msg in messages:
            try:
                data = orjson.loads(msg.get("data", "{}"))
                event = MarketLifecycleEvent.model_validate(data)
                events.append(event)
            except Exception:
                logger.exception("lifecycle_parse_skip", msg_id=msg.get("id"))

        if not events:
            return

        retries = 0
        while retries < 3:
            try:
                async with get_connection(self._config.postgres) as conn:
                    async with conn.cursor() as cur:
                        for event in events:
                            row = event.to_db_row()
                            # Insert lifecycle event
                            await cur.execute(
                                """
                                INSERT INTO lifecycle_events (ts, market_ticker,
                                    market_id, status)
                                VALUES (%(ts)s, %(market_ticker)s,
                                        %(market_id)s, %(status)s)
                                """,
                                row,
                            )
                            # Also update market status in metadata table
                            await cur.execute(
                                """
                                UPDATE markets SET status = %(status)s,
                                    last_synced_at = NOW()
                                WHERE ticker = %(market_ticker)s
                                """,
                                {
                                    "status": event.status,
                                    "market_ticker": event.market_ticker,
                                },
                            )
                    await conn.commit()

                self._total_written += len(events)
                logger.debug("lifecycle_flushed", count=len(events))
                return

            except Exception:
                retries += 1
                logger.exception("lifecycle_flush_error", retry=retries)
                await asyncio.sleep(2 ** retries)

        logger.error("lifecycle_flush_failed_permanently", count=len(events))


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
    writer = LifecycleWriter(config)
    await writer.run()


if __name__ == "__main__":
    asyncio.run(main())
