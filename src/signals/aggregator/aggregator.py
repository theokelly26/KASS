"""Signal Aggregator — combines all individual signal streams into composite scores.

The brain of the signal layer. Maintains active signals per market, computes
weighted composite scores modified by the current microstructure regime, and
publishes actionable composite signals.
"""

from __future__ import annotations

import asyncio
import time

import orjson
import redis.asyncio as aioredis
import structlog

from src.cache.redis_client import get_redis
from src.cache.streams import RedisStreamConsumer
from src.config import get_config
from src.signals.base import BaseSignalProcessor
from src.signals.config import AGGREGATOR_CONFIG
from src.signals.models import (
    CompositeSignal,
    MarketRegime,
    Signal,
    SignalDirection,
    SignalUrgency,
)
from src.signals.streams import STREAM_ALL_SIGNALS, STREAM_COMPOSITE, SignalPublisher

logger = structlog.get_logger(__name__)

# Signal type weights — how much each signal contributes to composite
SIGNAL_WEIGHTS = {
    "flow_toxicity": 0.35,
    "flow_burst": 0.08,
    "flow_large_trade": 0.05,
    "oi_divergence": 0.30,
    "cross_market_propagation": 0.15,
    "signal_propagation": 0.10,
    "settlement_cascade": 0.15,
    "new_market_open": 0.02,
    "new_market_extreme_price": 0.05,
    "regime_change": 0.05,
}

# Regime modifiers — multiply signal weights based on current regime
REGIME_MODIFIERS: dict[MarketRegime, dict[str, float]] = {
    MarketRegime.DEAD: {
        "flow_toxicity": 0.5,
        "oi_divergence": 0.7,
        "cross_market_propagation": 1.2,
    },
    MarketRegime.QUIET: {
        "flow_toxicity": 0.8,
        "oi_divergence": 0.9,
        "cross_market_propagation": 1.1,
    },
    MarketRegime.ACTIVE: {
        "flow_toxicity": 1.0,
        "oi_divergence": 1.0,
        "cross_market_propagation": 1.0,
    },
    MarketRegime.INFORMED: {
        "flow_toxicity": 1.5,
        "oi_divergence": 1.3,
        "cross_market_propagation": 0.8,
    },
    MarketRegime.PRE_SETTLEMENT: {
        "flow_toxicity": 0.8,
        "oi_divergence": 0.5,
        "cross_market_propagation": 1.0,
    },
}


class SignalAggregator(BaseSignalProcessor):
    """
    Consumes all individual signal streams and produces composite signals.

    Consumes: kalshi:signals:all
    Publishes: kalshi:signals:composite
    """

    PROCESSOR_NAME = "aggregator"
    INPUT_STREAMS = [STREAM_ALL_SIGNALS]
    OUTPUT_STREAM = STREAM_COMPOSITE

    def __init__(
        self,
        redis_consumer: RedisStreamConsumer,
        signal_publisher: SignalPublisher,
        config: dict,
        redis: aioredis.Redis | None = None,
    ) -> None:
        super().__init__(redis_consumer, signal_publisher, config)
        self._redis = redis
        self.active_signals: dict[str, list[Signal]] = {}
        self.last_composite_publish: dict[str, float] = {}

    async def run(self) -> None:
        """Override run to add cleanup task."""
        tasks = []

        # Main consumption
        for stream in self.INPUT_STREAMS:
            consumer_name = f"{self.PROCESSOR_NAME}_{stream.replace(':', '_')}"
            tasks.append(
                asyncio.create_task(
                    self.consumer.consume(
                        stream=stream,
                        group=self.CONSUMER_GROUP,
                        consumer=consumer_name,
                        handler=lambda msgs, s=stream: self._handle_batch(s, msgs),
                        batch_size=100,
                    )
                )
            )

        # Cleanup loop
        tasks.append(asyncio.create_task(self._cleanup_loop()))
        # Stats loop
        tasks.append(asyncio.create_task(self._stats_loop()))

        self.logger.info("aggregator_starting", input_streams=self.INPUT_STREAMS)
        await asyncio.gather(*tasks)

    async def process_message(self, stream: str, message: dict) -> list[Signal]:
        try:
            if isinstance(message, str):
                signal = Signal.model_validate_json(message)
            else:
                signal = Signal.model_validate(message)
        except Exception:
            self.logger.debug("signal_parse_skip", stream=stream)
            return []

        ticker = signal.market_ticker

        # Add to active signals
        if ticker not in self.active_signals:
            self.active_signals[ticker] = []
        self.active_signals[ticker].append(signal)

        # Cap active signals per market
        max_signals = self.config.get("max_active_signals_per_market", 20)
        if len(self.active_signals[ticker]) > max_signals:
            self.active_signals[ticker] = self.active_signals[ticker][-max_signals:]

        # Prune expired signals
        self.active_signals[ticker] = [
            s for s in self.active_signals[ticker] if not s.is_expired()
        ]

        # Cooldown check
        now = time.time()
        last_pub = self.last_composite_publish.get(ticker, 0)
        cooldown = self.config.get("publish_cooldown", 10)
        if now - last_pub < cooldown:
            return []

        # Recompute composite
        composite = await self._compute_composite(ticker)

        if composite and abs(composite.composite_score) >= self.config["min_composite_score"]:
            await self._publish_composite(composite)
            self.last_composite_publish[ticker] = now

        return []  # Composites published separately

    async def _compute_composite(self, ticker: str) -> CompositeSignal | None:
        active = self.active_signals.get(ticker, [])
        if not active:
            return None

        regime = await self._get_regime(ticker)
        regime_mods = REGIME_MODIFIERS.get(regime, {})

        weighted_sum = 0.0
        total_weight = 0.0

        for signal in active:
            base_weight = SIGNAL_WEIGHTS.get(signal.signal_type, 0.1)
            regime_mod = regime_mods.get(signal.signal_type, 1.0)
            weight = base_weight * regime_mod * signal.confidence

            direction_mult = {
                SignalDirection.BUY_YES: 1.0,
                SignalDirection.BUY_NO: -1.0,
                SignalDirection.NEUTRAL: 0.0,
            }[signal.direction]

            weighted_sum += signal.strength * direction_mult * weight
            total_weight += weight

        if total_weight == 0:
            return None

        composite_score = max(-1.0, min(1.0, weighted_sum / total_weight))

        if composite_score > 0.1:
            direction = SignalDirection.BUY_YES
        elif composite_score < -0.1:
            direction = SignalDirection.BUY_NO
        else:
            direction = SignalDirection.NEUTRAL

        event_ticker = next(
            (s.event_ticker for s in active if s.event_ticker), None
        )
        series_ticker = next(
            (s.series_ticker for s in active if s.series_ticker), None
        )

        return CompositeSignal(
            market_ticker=ticker,
            event_ticker=event_ticker,
            series_ticker=series_ticker,
            direction=direction,
            composite_score=round(composite_score, 4),
            active_signals=active,
            regime=regime,
        )

    async def _get_regime(self, ticker: str) -> MarketRegime:
        """Read current regime from Redis cache."""
        if self._redis is None:
            return MarketRegime.UNKNOWN

        key = f"state:regime:{ticker}"
        raw = await self._redis.get(key)
        if raw is None:
            return MarketRegime.UNKNOWN

        try:
            data = orjson.loads(raw)
            return MarketRegime(data.get("regime", "unknown"))
        except (ValueError, KeyError):
            return MarketRegime.UNKNOWN

    async def _publish_composite(self, composite: CompositeSignal) -> None:
        """Publish to kalshi:signals:composite stream."""
        await self.publisher.publish_composite(
            STREAM_COMPOSITE, composite.to_redis_payload()
        )
        self.logger.info(
            "composite_published",
            market=composite.market_ticker,
            direction=composite.direction.value,
            score=composite.composite_score,
            signal_count=len(composite.active_signals),
            regime=composite.regime.value,
        )

    async def _cleanup_loop(self) -> None:
        """Periodically clean up markets with no active signals."""
        interval = self.config.get("cleanup_interval", 60)
        while True:
            await asyncio.sleep(interval)
            cleaned = 0
            for ticker in list(self.active_signals.keys()):
                self.active_signals[ticker] = [
                    s for s in self.active_signals[ticker] if not s.is_expired()
                ]
                if not self.active_signals[ticker]:
                    del self.active_signals[ticker]
                    cleaned += 1
            if cleaned:
                self.logger.debug("cleanup_done", markets_cleaned=cleaned)


async def main() -> None:
    """Entry point for the signal aggregator process."""
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

    aggregator = SignalAggregator(consumer, publisher, AGGREGATOR_CONFIG, redis=redis)
    await aggregator.run()


if __name__ == "__main__":
    asyncio.run(main())
