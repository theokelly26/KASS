"""Redis stream publish/consume helpers for Kalshi data pipeline."""

from __future__ import annotations

from collections.abc import Callable, Awaitable
from typing import Any

import redis.asyncio as aioredis
import structlog

from src.models import (
    KalshiTrade,
    KalshiTickerV2,
    OrderbookDelta,
    OrderbookSnapshot,
    MarketLifecycleEvent,
)

logger = structlog.get_logger(__name__)

# Stream names
STREAM_TRADES = "kalshi:trades"
STREAM_TICKER_V2 = "kalshi:ticker_v2"
STREAM_ORDERBOOK_DELTAS = "kalshi:orderbook:deltas"
STREAM_ORDERBOOK_SNAPSHOTS = "kalshi:orderbook:snapshots"
STREAM_LIFECYCLE = "kalshi:lifecycle"
STREAM_EVENT_LIFECYCLE = "kalshi:event_lifecycle"
STREAM_SYSTEM = "kalshi:system"

# Max stream length (approximate trimming)
STREAM_MAXLEN = 100_000


class RedisStreamPublisher:
    """Publishes parsed messages to appropriate Redis streams."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis
        self._msg_count: dict[str, int] = {}

    async def publish_trade(self, trade: KalshiTrade) -> str:
        """Publish a trade to the trades stream. Returns message ID."""
        msg_id = await self._redis.xadd(
            STREAM_TRADES,
            {"data": trade.to_redis_payload()},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
        self._increment(STREAM_TRADES)
        return msg_id

    async def publish_ticker(self, ticker: KalshiTickerV2) -> str:
        """Publish a ticker update to the ticker_v2 stream."""
        msg_id = await self._redis.xadd(
            STREAM_TICKER_V2,
            {"data": ticker.to_redis_payload()},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
        self._increment(STREAM_TICKER_V2)
        return msg_id

    async def publish_orderbook_delta(self, delta: OrderbookDelta) -> str:
        """Publish an orderbook delta."""
        msg_id = await self._redis.xadd(
            STREAM_ORDERBOOK_DELTAS,
            {"data": delta.to_redis_payload()},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
        self._increment(STREAM_ORDERBOOK_DELTAS)
        return msg_id

    async def publish_orderbook_snapshot(self, snapshot: OrderbookSnapshot) -> str:
        """Publish an orderbook snapshot."""
        msg_id = await self._redis.xadd(
            STREAM_ORDERBOOK_SNAPSHOTS,
            {"data": snapshot.to_redis_payload()},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
        self._increment(STREAM_ORDERBOOK_SNAPSHOTS)
        return msg_id

    async def publish_lifecycle(self, event: MarketLifecycleEvent) -> str:
        """Publish a market lifecycle event."""
        msg_id = await self._redis.xadd(
            STREAM_LIFECYCLE,
            {"data": event.to_redis_payload()},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
        self._increment(STREAM_LIFECYCLE)
        return msg_id

    async def publish_event_lifecycle(self, event: Any) -> str:
        """Publish an event-level lifecycle message."""
        msg_id = await self._redis.xadd(
            STREAM_EVENT_LIFECYCLE,
            {"data": event.to_redis_payload()},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
        self._increment(STREAM_EVENT_LIFECYCLE)
        return msg_id

    async def publish_system(self, payload: str) -> str:
        """Publish a system health/alert event."""
        msg_id = await self._redis.xadd(
            STREAM_SYSTEM,
            {"data": payload},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
        self._increment(STREAM_SYSTEM)
        return msg_id

    def _increment(self, stream: str) -> None:
        self._msg_count[stream] = self._msg_count.get(stream, 0) + 1

    def get_counts(self) -> dict[str, int]:
        """Return and reset message counts (for periodic stats logging)."""
        counts = dict(self._msg_count)
        self._msg_count.clear()
        return counts


class RedisStreamConsumer:
    """Consumes messages from Redis streams with consumer groups."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def ensure_group(self, stream: str, group: str) -> None:
        """Create consumer group if it doesn't exist."""
        try:
            await self._redis.xgroup_create(stream, group, id="0", mkstream=True)
            logger.info("consumer_group_created", stream=stream, group=group)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                pass  # Group already exists
            else:
                raise

    async def consume(
        self,
        stream: str,
        group: str,
        consumer: str,
        handler: Callable[[list[dict[str, Any]]], Awaitable[None]],
        batch_size: int = 100,
        block_ms: int = 5000,
    ) -> None:
        """
        Consume messages from a stream using consumer groups.

        Calls handler with batches of messages. Acknowledges after successful processing.
        Runs indefinitely.
        """
        await self.ensure_group(stream, group)

        # First, claim any pending messages (from previous crash)
        await self._process_pending(stream, group, consumer, handler, batch_size)

        # Then read new messages
        while True:
            try:
                results = await self._redis.xreadgroup(
                    groupname=group,
                    consumername=consumer,
                    streams={stream: ">"},
                    count=batch_size,
                    block=block_ms,
                )

                if not results:
                    continue

                for _stream_name, messages in results:
                    if not messages:
                        continue

                    msg_ids = []
                    parsed = []
                    for msg_id, fields in messages:
                        msg_ids.append(msg_id)
                        parsed.append({"id": msg_id, **fields})

                    try:
                        await handler(parsed)
                        # Acknowledge all messages in batch
                        if msg_ids:
                            await self._redis.xack(stream, group, *msg_ids)
                    except Exception:
                        logger.exception(
                            "handler_error",
                            stream=stream,
                            batch_size=len(parsed),
                        )
                        # Don't ack — messages will be redelivered

            except aioredis.ConnectionError:
                logger.error("redis_connection_lost", stream=stream)
                import asyncio
                await asyncio.sleep(5)
            except Exception:
                logger.exception("consumer_error", stream=stream)
                import asyncio
                await asyncio.sleep(1)

    async def _process_pending(
        self,
        stream: str,
        group: str,
        consumer: str,
        handler: Callable[[list[dict[str, Any]]], Awaitable[None]],
        batch_size: int,
    ) -> None:
        """Process any pending messages from a previous crash."""
        while True:
            results = await self._redis.xreadgroup(
                groupname=group,
                consumername=consumer,
                streams={stream: "0"},
                count=batch_size,
            )

            if not results:
                break

            for _stream_name, messages in results:
                if not messages:
                    return  # No more pending

                msg_ids = []
                parsed = []
                for msg_id, fields in messages:
                    if not fields:
                        # Already acknowledged but still in PEL — skip
                        continue
                    msg_ids.append(msg_id)
                    parsed.append({"id": msg_id, **fields})

                if parsed:
                    try:
                        await handler(parsed)
                        if msg_ids:
                            await self._redis.xack(stream, group, *msg_ids)
                        logger.info(
                            "pending_messages_processed",
                            stream=stream,
                            count=len(parsed),
                        )
                    except Exception:
                        logger.exception("pending_handler_error", stream=stream)
                        return  # Stop processing pending, move to new messages
                else:
                    return
