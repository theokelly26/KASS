"""Lifecycle Alpha Scanner — detects opportunities around market lifecycle transitions.

Patterns: new market premium, settlement cascade, status change momentum.
"""

from __future__ import annotations

import asyncio
import time

import structlog

from src.cache.redis_client import get_redis
from src.cache.streams import STREAM_LIFECYCLE, STREAM_TICKER_V2, RedisStreamConsumer
from src.config import get_config
from src.discovery.series_mapper import SeriesMapper
from src.models import KalshiTickerV2, MarketLifecycleEvent
from src.signals.base import BaseSignalProcessor
from src.signals.config import LIFECYCLE_CONFIG
from src.signals.models import Signal, SignalDirection, SignalUrgency
from src.signals.streams import SignalPublisher

logger = structlog.get_logger(__name__)


class LifecycleAlphaScanner(BaseSignalProcessor):
    """
    Detects alpha opportunities around market lifecycle transitions.

    Consumes: kalshi:lifecycle, kalshi:ticker_v2
    Publishes: kalshi:signals:lifecycle
    """

    PROCESSOR_NAME = "lifecycle_alpha"
    INPUT_STREAMS = [STREAM_LIFECYCLE, STREAM_TICKER_V2]
    OUTPUT_STREAM = "kalshi:signals:lifecycle"

    def __init__(
        self,
        redis_consumer: RedisStreamConsumer,
        signal_publisher: SignalPublisher,
        config: dict,
        series_mapper: SeriesMapper | None = None,
    ) -> None:
        super().__init__(redis_consumer, signal_publisher, config)
        self.series_mapper = series_mapper
        self.recent_settlements: dict[str, float] = {}  # event_ticker -> timestamp
        self.recent_opens: dict[str, float] = {}  # market_ticker -> timestamp

    async def process_message(self, stream: str, message: dict) -> list[Signal]:
        signals: list[Signal] = []

        if stream == STREAM_LIFECYCLE:
            event = MarketLifecycleEvent.model_validate(message)

            if event.event_type == "open":
                self.recent_opens[event.market_ticker] = time.time()
                new_signals = await self._check_new_market_premium(event)
                signals.extend(new_signals)

            elif event.event_type in ("settled", "closed", "determined"):
                cascade_signals = await self._check_settlement_cascade(event)
                signals.extend(cascade_signals)

        elif stream == STREAM_TICKER_V2:
            ticker = KalshiTickerV2.model_validate(message)
            if ticker.market_ticker in self.recent_opens:
                open_time = self.recent_opens[ticker.market_ticker]
                if time.time() - open_time < self.config.get("new_market_window", 300):
                    new_signals = await self._evaluate_new_market_price(ticker)
                    signals.extend(new_signals)

        return signals

    async def _check_new_market_premium(
        self, event: MarketLifecycleEvent
    ) -> list[Signal]:
        """Flag newly opened markets for monitoring — early prices are often mispriced."""
        return [
            Signal(
                signal_type="new_market_open",
                market_ticker=event.market_ticker,
                direction=SignalDirection.NEUTRAL,
                strength=0.4,
                confidence=0.4,
                urgency=SignalUrgency.WATCH,
                metadata={
                    "pattern": "new_market_premium",
                    "status": event.event_type,
                    "opened_at": time.time(),
                },
                ttl_seconds=self.config.get("new_market_window", 300),
            )
        ]

    async def _check_settlement_cascade(
        self, event: MarketLifecycleEvent
    ) -> list[Signal]:
        """When a market settles, related markets may need to reprice."""
        if self.series_mapper is None:
            return []

        related = await self.series_mapper.get_related_markets(event.market_ticker)
        if not related:
            return []

        signals = []
        for ticker in related:
            if ticker == event.market_ticker:
                continue
            signals.append(
                Signal(
                    signal_type="settlement_cascade",
                    market_ticker=ticker,
                    direction=SignalDirection.NEUTRAL,
                    strength=0.6,
                    confidence=0.5,
                    urgency=SignalUrgency.IMMEDIATE,
                    metadata={
                        "settled_market": event.market_ticker,
                        "settled_status": event.event_type,
                        "pattern": "settlement_cascade",
                    },
                    ttl_seconds=self.config.get("settlement_cascade_window", 120),
                )
            )

        if signals:
            logger.info(
                "settlement_cascade_detected",
                settled_market=event.market_ticker,
                related_count=len(signals),
            )

        return signals

    async def _evaluate_new_market_price(
        self, ticker: KalshiTickerV2
    ) -> list[Signal]:
        """Evaluate initial pricing of a recently opened market."""
        if ticker.price is None:
            return []

        signals = []

        # Directional new_market_open signal if price is far from 50
        # (contrarian mean-reversion bet on initial mispricing)
        distance_from_mid = abs(ticker.price - 50)
        if distance_from_mid >= 15:
            direction = (
                SignalDirection.BUY_NO if ticker.price > 50
                else SignalDirection.BUY_YES
            )
            signals.append(
                Signal(
                    signal_type="new_market_open",
                    market_ticker=ticker.market_ticker,
                    direction=direction,
                    strength=min(1.0, distance_from_mid / 50.0),
                    confidence=min(0.6, 0.3 + (distance_from_mid / 100.0)),
                    urgency=SignalUrgency.WATCH,
                    metadata={
                        "initial_price": ticker.price,
                        "distance_from_mid": distance_from_mid,
                        "pattern": "new_market_directional",
                    },
                    ttl_seconds=self.config.get("new_market_window", 300),
                )
            )

        # Flag extreme initial prices as potential mispricing
        if ticker.price <= 20 or ticker.price >= 80:
            signals.append(
                Signal(
                    signal_type="new_market_extreme_price",
                    market_ticker=ticker.market_ticker,
                    direction=(
                        SignalDirection.BUY_NO
                        if ticker.price >= 80
                        else SignalDirection.BUY_YES
                    ),
                    strength=0.5,
                    confidence=0.35,
                    urgency=SignalUrgency.WATCH,
                    metadata={
                        "initial_price": ticker.price,
                        "pattern": "new_market_extreme_price",
                    },
                    ttl_seconds=self.config.get("new_market_window", 300),
                )
            )
        return signals


async def main() -> None:
    """Entry point for the lifecycle alpha scanner process."""
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
    )

    from src.persistence.db import get_pool

    config = get_config()
    redis = await get_redis(config.redis)
    consumer = RedisStreamConsumer(redis)
    publisher = SignalPublisher(redis)
    series_mapper = SeriesMapper(redis, config.postgres)

    processor = LifecycleAlphaScanner(
        consumer, publisher, LIFECYCLE_CONFIG, series_mapper=series_mapper
    )
    await processor.run()


if __name__ == "__main__":
    asyncio.run(main())
