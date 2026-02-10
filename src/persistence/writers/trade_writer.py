"""Consumes trades from Redis stream and batch-inserts into TimescaleDB."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import orjson
import structlog

from src.cache.redis_client import get_redis
from src.cache.streams import STREAM_TRADES, RedisStreamConsumer
from src.config import AppConfig, get_config
from src.models import KalshiTrade
from src.persistence.db import get_connection

logger = structlog.get_logger(__name__)

CONSUMER_GROUP = "db_writers"
CONSUMER_NAME = "trade_writer_1"


class TradeWriter:
    """
    Consumes from kalshi:trades Redis stream.
    Batch-inserts into trades hypertable.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._batch: list[KalshiTrade] = []
        self._last_flush = time.time()
        self._total_written = 0

    async def run(self) -> None:
        """Main consumer loop."""
        redis = await get_redis(self._config.redis)
        consumer = RedisStreamConsumer(redis)

        logger.info("trade_writer_started")

        await consumer.consume(
            stream=STREAM_TRADES,
            group=CONSUMER_GROUP,
            consumer=CONSUMER_NAME,
            handler=self._handle_batch,
            batch_size=self._config.tuning.trade_writer_batch_size,
        )

    async def _handle_batch(self, messages: list[dict[str, Any]]) -> None:
        """Process a batch of messages from the stream."""
        trades = []
        for msg in messages:
            try:
                data = orjson.loads(msg.get("data", "{}"))
                trade = KalshiTrade.model_validate(data)
                trades.append(trade)
            except Exception:
                logger.exception("trade_parse_skip", msg_id=msg.get("id"))

        if trades:
            await self._flush_batch(trades)

    async def _flush_batch(self, trades: list[KalshiTrade]) -> None:
        """Insert batch into TimescaleDB with deduplication."""
        if not trades:
            return

        retries = 0
        while retries < 3:
            try:
                async with get_connection(self._config.postgres) as conn:
                    async with conn.cursor() as cur:
                        for trade in trades:
                            row = trade.to_db_row()
                            await cur.execute(
                                """
                                INSERT INTO trades (ts, trade_id, market_ticker, yes_price,
                                                    no_price, count, taker_side)
                                VALUES (%(ts)s, %(trade_id)s, %(market_ticker)s, %(yes_price)s,
                                        %(no_price)s, %(count)s, %(taker_side)s)
                                ON CONFLICT DO NOTHING
                                """,
                                row,
                            )
                    await conn.commit()

                self._total_written += len(trades)
                logger.debug("trades_flushed", count=len(trades), total=self._total_written)
                return

            except Exception:
                retries += 1
                logger.exception("trade_flush_error", retry=retries)
                await asyncio.sleep(2 ** retries)

        logger.error("trade_flush_failed_permanently", count=len(trades))


async def main() -> None:
    """Entry point for the trade writer process."""
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
    writer = TradeWriter(config)
    await writer.run()


if __name__ == "__main__":
    asyncio.run(main())
