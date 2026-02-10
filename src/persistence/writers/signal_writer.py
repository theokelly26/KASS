"""Consumes signals and composites from Redis streams and persists to TimescaleDB."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Any

import orjson
import structlog

from src.cache.redis_client import get_redis
from src.cache.streams import RedisStreamConsumer
from src.config import AppConfig, get_config
from src.persistence.db import get_connection
from src.signals.streams import STREAM_ALL_SIGNALS, STREAM_COMPOSITE, STREAM_REGIME

logger = structlog.get_logger(__name__)

CONSUMER_GROUP = "db_writers"


class SignalWriter:
    """
    Consumes from kalshi:signals:all and writes to signal_log table.
    """

    CONSUMER_NAME = "signal_writer_1"

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._total_written = 0

    async def run(self) -> None:
        redis = await get_redis(self._config.redis)
        consumer = RedisStreamConsumer(redis)

        logger.info("signal_writer_started")

        await consumer.consume(
            stream=STREAM_ALL_SIGNALS,
            group=CONSUMER_GROUP,
            consumer=self.CONSUMER_NAME,
            handler=self._handle_batch,
            batch_size=50,
        )

    async def _handle_batch(self, messages: list[dict[str, Any]]) -> None:
        rows = []
        for msg in messages:
            try:
                data = orjson.loads(msg.get("data", "{}"))
                ts_raw = data.get("ts")
                if isinstance(ts_raw, str):
                    ts = datetime.fromisoformat(ts_raw)
                elif isinstance(ts_raw, (int, float)):
                    ts = datetime.fromtimestamp(ts_raw, tz=timezone.utc)
                else:
                    ts = datetime.now(tz=timezone.utc)

                ttl = data.get("ttl_seconds", 300)
                rows.append({
                    "ts": ts,
                    "signal_id": data.get("signal_id", ""),
                    "signal_type": data.get("signal_type", ""),
                    "market_ticker": data.get("market_ticker", ""),
                    "event_ticker": data.get("event_ticker"),
                    "series_ticker": data.get("series_ticker"),
                    "direction": data.get("direction", "neutral"),
                    "strength": data.get("strength", 0.0),
                    "confidence": data.get("confidence", 0.0),
                    "urgency": data.get("urgency", "background"),
                    "metadata": orjson.dumps(data.get("metadata", {})).decode(),
                    "ttl_seconds": ttl,
                    "expired_at": ts + timedelta(seconds=ttl),
                })
            except Exception:
                logger.exception("signal_parse_skip", msg_id=msg.get("id"))

        if rows:
            await self._flush(rows)

    async def _flush(self, rows: list[dict]) -> None:
        retries = 0
        while retries < 3:
            try:
                async with get_connection(self._config.postgres) as conn:
                    async with conn.cursor() as cur:
                        for row in rows:
                            await cur.execute(
                                """
                                INSERT INTO signal_log (ts, signal_id, signal_type, market_ticker,
                                    event_ticker, series_ticker, direction, strength, confidence,
                                    urgency, metadata, ttl_seconds, expired_at)
                                VALUES (%(ts)s, %(signal_id)s, %(signal_type)s, %(market_ticker)s,
                                    %(event_ticker)s, %(series_ticker)s, %(direction)s, %(strength)s,
                                    %(confidence)s, %(urgency)s, %(metadata)s, %(ttl_seconds)s,
                                    %(expired_at)s)
                                ON CONFLICT DO NOTHING
                                """,
                                row,
                            )
                    await conn.commit()

                self._total_written += len(rows)
                logger.debug("signals_flushed", count=len(rows), total=self._total_written)
                return
            except Exception:
                retries += 1
                logger.exception("signal_flush_error", retry=retries)
                await asyncio.sleep(2 ** retries)

        logger.error("signal_flush_failed_permanently", count=len(rows))


class CompositeWriter:
    """
    Consumes from kalshi:signals:composite and writes to composite_log table.
    """

    CONSUMER_NAME = "composite_writer_1"

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._total_written = 0

    async def run(self) -> None:
        redis = await get_redis(self._config.redis)
        consumer = RedisStreamConsumer(redis)

        logger.info("composite_writer_started")

        await consumer.consume(
            stream=STREAM_COMPOSITE,
            group=CONSUMER_GROUP,
            consumer=self.CONSUMER_NAME,
            handler=self._handle_batch,
            batch_size=50,
        )

    async def _handle_batch(self, messages: list[dict[str, Any]]) -> None:
        rows = []
        for msg in messages:
            try:
                data = orjson.loads(msg.get("data", "{}"))
                ts_raw = data.get("ts")
                if isinstance(ts_raw, str):
                    ts = datetime.fromisoformat(ts_raw)
                elif isinstance(ts_raw, (int, float)):
                    ts = datetime.fromtimestamp(ts_raw, tz=timezone.utc)
                else:
                    ts = datetime.now(tz=timezone.utc)

                active_signals = data.get("active_signals", [])
                signal_ids = [s.get("signal_id", "") for s in active_signals]

                rows.append({
                    "ts": ts,
                    "market_ticker": data.get("market_ticker", ""),
                    "event_ticker": data.get("event_ticker"),
                    "series_ticker": data.get("series_ticker"),
                    "direction": data.get("direction", "neutral"),
                    "composite_score": data.get("composite_score", 0.0),
                    "regime": data.get("regime", "unknown"),
                    "active_signal_count": len(active_signals),
                    "active_signal_ids": signal_ids,
                })
            except Exception:
                logger.exception("composite_parse_skip", msg_id=msg.get("id"))

        if rows:
            await self._flush(rows)

    async def _flush(self, rows: list[dict]) -> None:
        retries = 0
        while retries < 3:
            try:
                async with get_connection(self._config.postgres) as conn:
                    async with conn.cursor() as cur:
                        for row in rows:
                            await cur.execute(
                                """
                                INSERT INTO composite_log (ts, market_ticker, event_ticker,
                                    series_ticker, direction, composite_score, regime,
                                    active_signal_count, active_signal_ids)
                                VALUES (%(ts)s, %(market_ticker)s, %(event_ticker)s,
                                    %(series_ticker)s, %(direction)s, %(composite_score)s,
                                    %(regime)s, %(active_signal_count)s, %(active_signal_ids)s)
                                """,
                                row,
                            )
                    await conn.commit()

                self._total_written += len(rows)
                logger.debug("composites_flushed", count=len(rows), total=self._total_written)
                return
            except Exception:
                retries += 1
                logger.exception("composite_flush_error", retry=retries)
                await asyncio.sleep(2 ** retries)

        logger.error("composite_flush_failed_permanently", count=len(rows))


class RegimeWriter:
    """
    Consumes from kalshi:signals:regime and writes to regime_log table.
    """

    CONSUMER_NAME = "regime_writer_1"

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._total_written = 0

    async def run(self) -> None:
        redis = await get_redis(self._config.redis)
        consumer = RedisStreamConsumer(redis)

        logger.info("regime_writer_started")

        await consumer.consume(
            stream=STREAM_REGIME,
            group=CONSUMER_GROUP,
            consumer=self.CONSUMER_NAME,
            handler=self._handle_batch,
            batch_size=50,
        )

    async def _handle_batch(self, messages: list[dict[str, Any]]) -> None:
        rows = []
        for msg in messages:
            try:
                data = orjson.loads(msg.get("data", "{}"))
                ts_raw = data.get("ts")
                if isinstance(ts_raw, str):
                    ts = datetime.fromisoformat(ts_raw)
                elif isinstance(ts_raw, (int, float)):
                    ts = datetime.fromtimestamp(ts_raw, tz=timezone.utc)
                else:
                    ts = datetime.now(tz=timezone.utc)

                metadata = data.get("metadata", {})
                rows.append({
                    "ts": ts,
                    "market_ticker": data.get("market_ticker", ""),
                    "old_regime": metadata.get("old_regime"),
                    "new_regime": metadata.get("new_regime", data.get("direction", "unknown")),
                    "trade_rate": metadata.get("trade_rate"),
                    "message_rate": metadata.get("message_rate"),
                    "depth_imbalance": metadata.get("depth_imbalance"),
                })
            except Exception:
                logger.exception("regime_parse_skip", msg_id=msg.get("id"))

        if rows:
            await self._flush(rows)

    async def _flush(self, rows: list[dict]) -> None:
        retries = 0
        while retries < 3:
            try:
                async with get_connection(self._config.postgres) as conn:
                    async with conn.cursor() as cur:
                        for row in rows:
                            await cur.execute(
                                """
                                INSERT INTO regime_log (ts, market_ticker, old_regime,
                                    new_regime, trade_rate, message_rate, depth_imbalance)
                                VALUES (%(ts)s, %(market_ticker)s, %(old_regime)s,
                                    %(new_regime)s, %(trade_rate)s, %(message_rate)s,
                                    %(depth_imbalance)s)
                                """,
                                row,
                            )
                    await conn.commit()

                self._total_written += len(rows)
                logger.debug("regimes_flushed", count=len(rows), total=self._total_written)
                return
            except Exception:
                retries += 1
                logger.exception("regime_flush_error", retry=retries)
                await asyncio.sleep(2 ** retries)

        logger.error("regime_flush_failed_permanently", count=len(rows))


async def main() -> None:
    """Entry point: runs signal, composite, and regime writers concurrently."""
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
    signal_writer = SignalWriter(config)
    composite_writer = CompositeWriter(config)
    regime_writer = RegimeWriter(config)

    await asyncio.gather(
        signal_writer.run(),
        composite_writer.run(),
        regime_writer.run(),
    )


if __name__ == "__main__":
    asyncio.run(main())
