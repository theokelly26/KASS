"""Signal-specific Redis stream helpers for publishing and querying signals."""

from __future__ import annotations

import time
from typing import Any

import orjson
import redis.asyncio as aioredis
import structlog

from src.signals.models import Signal

logger = structlog.get_logger(__name__)

# Signal stream names
STREAM_FLOW_TOXICITY = "kalshi:signals:flow_toxicity"
STREAM_OI_DIVERGENCE = "kalshi:signals:oi_divergence"
STREAM_REGIME = "kalshi:signals:regime"
STREAM_CROSS_MARKET = "kalshi:signals:cross_market"
STREAM_LIFECYCLE = "kalshi:signals:lifecycle"
STREAM_ALL_SIGNALS = "kalshi:signals:all"
STREAM_COMPOSITE = "kalshi:signals:composite"

SIGNAL_MAXLEN = 10_000

ALL_SIGNAL_STREAMS = [
    STREAM_FLOW_TOXICITY,
    STREAM_OI_DIVERGENCE,
    STREAM_REGIME,
    STREAM_CROSS_MARKET,
    STREAM_LIFECYCLE,
]


class SignalPublisher:
    """Publishes signals to Redis streams with MAXLEN trimming."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def publish(self, stream: str, signal: Signal) -> str:
        """Publish signal, trim stream to MAXLEN ~10000."""
        msg_id = await self._redis.xadd(
            stream,
            {"data": signal.to_redis_payload()},
            maxlen=SIGNAL_MAXLEN,
            approximate=True,
        )
        return msg_id

    async def publish_composite(self, stream: str, payload: str) -> str:
        """Publish a composite signal payload."""
        msg_id = await self._redis.xadd(
            stream,
            {"data": payload},
            maxlen=SIGNAL_MAXLEN,
            approximate=True,
        )
        return msg_id

    async def get_recent_signals(
        self, stream: str, count: int = 100
    ) -> list[Signal]:
        """Read recent signals from a stream."""
        messages = await self._redis.xrevrange(stream, count=count)
        signals = []
        for _msg_id, fields in messages:
            try:
                data = fields.get("data", "{}")
                signal = Signal.model_validate_json(data)
                signals.append(signal)
            except Exception:
                logger.debug("signal_parse_skip", stream=stream)
        return signals

    async def get_active_signals_for_market(
        self, market_ticker: str
    ) -> list[Signal]:
        """Get all non-expired signals for a specific market across all signal streams."""
        active: list[Signal] = []

        for stream in ALL_SIGNAL_STREAMS:
            try:
                signals = await self.get_recent_signals(stream, count=200)
                for s in signals:
                    if s.market_ticker == market_ticker and not s.is_expired():
                        active.append(s)
            except Exception:
                logger.debug("stream_read_error", stream=stream)

        return active
