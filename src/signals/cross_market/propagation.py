"""Cross-Market Propagation Engine — detects repricing opportunities across related markets.

When a signal fires on one market in an event/series, checks whether related
markets have repriced accordingly. If they haven't, that's the opportunity.
"""

from __future__ import annotations

import asyncio
import time

import structlog

from src.cache.redis_client import get_redis
from src.cache.streams import STREAM_TICKER_V2, RedisStreamConsumer
from src.config import get_config
from src.discovery.series_mapper import SeriesMapper
from src.models import KalshiTickerV2
from src.signals.base import BaseSignalProcessor
from src.signals.config import CROSS_MARKET_CONFIG
from src.signals.models import Signal, SignalDirection, SignalUrgency
from src.signals.streams import (
    STREAM_FLOW_TOXICITY,
    STREAM_OI_DIVERGENCE,
    SignalPublisher,
)

logger = structlog.get_logger(__name__)


class CrossMarketPropagationEngine(BaseSignalProcessor):
    """
    Detects when a price move or flow signal in one market within an event
    hasn't propagated to related markets in the same event/series.

    Consumes: kalshi:signals:flow_toxicity, kalshi:signals:oi_divergence,
              kalshi:ticker_v2
    Publishes: kalshi:signals:cross_market
    """

    PROCESSOR_NAME = "cross_market"
    INPUT_STREAMS = [STREAM_FLOW_TOXICITY, STREAM_OI_DIVERGENCE, STREAM_TICKER_V2]
    OUTPUT_STREAM = "kalshi:signals:cross_market"

    def __init__(
        self,
        redis_consumer: RedisStreamConsumer,
        signal_publisher: SignalPublisher,
        config: dict,
        series_mapper: SeriesMapper | None = None,
    ) -> None:
        super().__init__(redis_consumer, signal_publisher, config)
        self.series_mapper = series_mapper
        self.market_prices: dict[str, int] = {}
        self.price_move_timestamps: dict[str, float] = {}
        # Cache for event_ticker lookups
        self._event_ticker_cache: dict[str, str | None] = {}

    async def process_message(self, stream: str, message: dict) -> list[Signal]:
        signals: list[Signal] = []

        if stream == STREAM_TICKER_V2:
            ticker = KalshiTickerV2.model_validate(message)
            if ticker.price is not None:
                old_price = self.market_prices.get(ticker.market_ticker)
                self.market_prices[ticker.market_ticker] = ticker.price

                if old_price is not None:
                    move = abs(ticker.price - old_price)
                    if move >= self.config["min_price_move"]:
                        self.price_move_timestamps[ticker.market_ticker] = time.time()
                        prop_signals = await self._check_propagation(
                            ticker.market_ticker, old_price, ticker.price
                        )
                        signals.extend(prop_signals)

        elif stream in (STREAM_FLOW_TOXICITY, STREAM_OI_DIVERGENCE):
            # A signal fired on a specific market — check related markets
            try:
                signal = Signal.model_validate_json(
                    message if isinstance(message, str) else message.get("data", "{}")
                )
                if signal.direction != SignalDirection.NEUTRAL:
                    if signal.strength >= self.config.get("min_source_strength", 0.5):
                        prop_signals = await self._check_signal_propagation(signal)
                        signals.extend(prop_signals)
            except Exception:
                self.logger.debug("signal_parse_skip", stream=stream)

        return signals

    async def _check_propagation(
        self, moved_ticker: str, old_price: int, new_price: int
    ) -> list[Signal]:
        """A market moved. Check if related markets should also move."""
        if self.series_mapper is None:
            return []

        related = await self.series_mapper.get_related_markets(moved_ticker)
        if not related or len(related) > self.config.get("max_related_markets", 20):
            return []

        signals = []
        move_direction = "up" if new_price > old_price else "down"
        move_magnitude = abs(new_price - old_price)
        moved_at = self.price_move_timestamps.get(moved_ticker, time.time())

        for related_ticker in related:
            if related_ticker == moved_ticker:
                continue

            related_price = self.market_prices.get(related_ticker)
            if related_price is None:
                continue

            related_last_move = self.price_move_timestamps.get(related_ticker, 0)
            time_since_related_move = moved_at - related_last_move

            if time_since_related_move > self.config["propagation_window"]:
                expected_direction = self._infer_expected_direction(
                    moved_ticker, related_ticker, move_direction
                )
                if expected_direction:
                    event_ticker = self._event_ticker_cache.get(related_ticker)
                    signals.append(
                        Signal(
                            signal_type="cross_market_propagation",
                            market_ticker=related_ticker,
                            event_ticker=event_ticker,
                            direction=expected_direction,
                            strength=min(1.0, move_magnitude / 10.0),
                            confidence=0.65,
                            urgency=SignalUrgency.IMMEDIATE,
                            metadata={
                                "source_market": moved_ticker,
                                "source_old_price": old_price,
                                "source_new_price": new_price,
                                "target_current_price": related_price,
                                "propagation_lag_seconds": round(
                                    time_since_related_move, 1
                                ),
                                "move_magnitude": move_magnitude,
                            },
                        )
                    )

        return signals

    def _infer_expected_direction(
        self, source: str, target: str, source_direction: str
    ) -> SignalDirection | None:
        """
        Given that source moved in source_direction, what should target do?

        Simplified: same-event markets move in the same direction.
        Full bracket parsing is a Phase 2.5 refinement.
        """
        if source_direction == "up":
            return SignalDirection.BUY_YES
        else:
            return SignalDirection.BUY_NO

    async def _check_signal_propagation(self, signal: Signal) -> list[Signal]:
        """
        A flow/OI signal fired on a market. Check if related markets
        show similar signals or have repriced. If not, propagate.
        """
        if self.series_mapper is None:
            return []

        related = await self.series_mapper.get_related_markets(signal.market_ticker)
        if not related:
            return []

        attenuation = self.config.get("signal_attenuation", 0.7)
        conf_attenuation = self.config.get("confidence_attenuation", 0.6)

        signals = []
        for related_ticker in related:
            if related_ticker == signal.market_ticker:
                continue

            # Check if related market already has active signals
            existing = await self.publisher.get_active_signals_for_market(
                related_ticker
            )
            if any(
                s.signal_type in ("flow_toxicity", "oi_divergence") for s in existing
            ):
                continue  # Already signaled

            # Check if related market has repriced recently
            related_last_move = self.price_move_timestamps.get(related_ticker, 0)
            if time.time() - related_last_move > self.config["propagation_window"]:
                signals.append(
                    Signal(
                        signal_type="signal_propagation",
                        market_ticker=related_ticker,
                        event_ticker=signal.event_ticker,
                        direction=signal.direction,
                        strength=signal.strength * attenuation,
                        confidence=signal.confidence * conf_attenuation,
                        urgency=SignalUrgency.WATCH,
                        metadata={
                            "source_signal_id": signal.signal_id,
                            "source_signal_type": signal.signal_type,
                            "source_market": signal.market_ticker,
                            "attenuation": attenuation,
                        },
                    )
                )

        return signals


async def main() -> None:
    """Entry point for the cross-market propagation engine."""
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
    redis = await get_redis(config.redis)
    consumer = RedisStreamConsumer(redis)
    publisher = SignalPublisher(redis)
    series_mapper = SeriesMapper(redis, config.postgres)

    processor = CrossMarketPropagationEngine(
        consumer, publisher, CROSS_MARKET_CONFIG, series_mapper=series_mapper
    )
    await processor.run()


if __name__ == "__main__":
    asyncio.run(main())
