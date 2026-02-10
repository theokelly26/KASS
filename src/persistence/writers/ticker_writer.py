"""Consumes ticker_v2 updates from Redis stream and writes to TimescaleDB."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import orjson
import structlog

from src.cache.redis_client import get_redis
from src.cache.streams import STREAM_TICKER_V2, RedisStreamConsumer
from src.config import AppConfig, get_config
from src.models import KalshiTickerV2
from src.persistence.db import get_connection

logger = structlog.get_logger(__name__)

CONSUMER_GROUP = "db_writers"
CONSUMER_NAME = "ticker_writer_1"


class TickerWriter:
    """
    Consumes from kalshi:ticker_v2 Redis stream.
    Batch-inserts into ticker_updates hypertable.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._total_written = 0

    async def run(self) -> None:
        """Main consumer loop."""
        redis = await get_redis(self._config.redis)
        consumer = RedisStreamConsumer(redis)

        logger.info("ticker_writer_started")

        await consumer.consume(
            stream=STREAM_TICKER_V2,
            group=CONSUMER_GROUP,
            consumer=CONSUMER_NAME,
            handler=self._handle_batch,
            batch_size=100,
        )

    async def _handle_batch(self, messages: list[dict[str, Any]]) -> None:
        """Process a batch of ticker messages."""
        tickers = []
        for msg in messages:
            try:
                data = orjson.loads(msg.get("data", "{}"))
                ticker = KalshiTickerV2.model_validate(data)
                tickers.append(ticker)
            except Exception:
                logger.exception("ticker_parse_skip", msg_id=msg.get("id"))

        if tickers:
            await self._flush_batch(tickers)

    async def _flush_batch(self, tickers: list[KalshiTickerV2]) -> None:
        """Insert batch into TimescaleDB."""
        retries = 0
        while retries < 3:
            try:
                async with get_connection(self._config.postgres) as conn:
                    async with conn.cursor() as cur:
                        for t in tickers:
                            row = t.to_db_row()
                            await cur.execute(
                                """
                                INSERT INTO ticker_updates (ts, market_ticker, price,
                                    volume_delta, open_interest_delta,
                                    dollar_volume_delta, dollar_open_interest_delta)
                                VALUES (%(ts)s, %(market_ticker)s, %(price)s,
                                        %(volume_delta)s, %(open_interest_delta)s,
                                        %(dollar_volume_delta)s, %(dollar_open_interest_delta)s)
                                """,
                                row,
                            )
                    await conn.commit()

                self._total_written += len(tickers)
                logger.debug("tickers_flushed", count=len(tickers), total=self._total_written)
                return

            except Exception:
                retries += 1
                logger.exception("ticker_flush_error", retry=retries)
                await asyncio.sleep(2 ** retries)

        logger.error("ticker_flush_failed_permanently", count=len(tickers))


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
    writer = TickerWriter(config)
    await writer.run()


if __name__ == "__main__":
    asyncio.run(main())
