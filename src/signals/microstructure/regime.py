"""Microstructure Regime Detector — classifies each market's current state.

This is a meta-signal that tells other processors and future execution
logic how to behave. Not directional — it describes the market's character.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque

import orjson
import redis.asyncio as aioredis
import structlog

from src.cache.redis_client import get_redis
from src.cache.streams import STREAM_ORDERBOOK_DELTAS, STREAM_TRADES, STREAM_TICKER_V2
from src.cache.streams import RedisStreamConsumer
from src.config import get_config
from src.models import KalshiTrade, KalshiTickerV2, OrderbookDelta
from src.signals.base import BaseSignalProcessor
from src.signals.config import REGIME_CONFIG
from src.signals.models import MarketRegime, Signal, SignalDirection, SignalUrgency
from src.signals.streams import SignalPublisher

logger = structlog.get_logger(__name__)

KEY_REGIME = "state:regime:{ticker}"


class RegimeMarketState:
    """Per-market state for regime classification."""

    def __init__(self) -> None:
        # Orderbook state
        self.current_spread: int | None = None
        self.yes_depth: int = 0
        self.no_depth: int = 0
        self.depth_ratio: float = 1.0

        # Message rate tracking
        self.delta_timestamps: deque[float] = deque(maxlen=200)
        self.trade_timestamps: deque[float] = deque(maxlen=200)

        # Price tracking
        self.last_price: int | None = None
        self.prices: deque[int] = deque(maxlen=50)

        # Regime history
        self.previous_regime: MarketRegime = MarketRegime.UNKNOWN
        self.regime_history: deque[tuple[float, MarketRegime]] = deque(maxlen=100)

    def update_from_delta(self, delta: OrderbookDelta) -> None:
        self.delta_timestamps.append(time.time())
        delta_qty = int(float(delta.delta_fp))
        if delta.side == "yes":
            self.yes_depth = max(0, self.yes_depth + delta_qty)
        else:
            self.no_depth = max(0, self.no_depth + delta_qty)
        if self.no_depth > 0:
            self.depth_ratio = self.yes_depth / self.no_depth

    def update_from_trade(self, trade: KalshiTrade) -> None:
        self.trade_timestamps.append(time.time())
        self.last_price = trade.yes_price
        self.prices.append(trade.yes_price)

    def update_from_ticker(self, ticker: KalshiTickerV2) -> None:
        if ticker.price is not None:
            self.last_price = ticker.price
            self.prices.append(ticker.price)

    @property
    def message_rate(self) -> float:
        """Messages per second over last 60 seconds."""
        now = time.time()
        all_ts = list(self.delta_timestamps) + list(self.trade_timestamps)
        recent = [t for t in all_ts if now - t <= 60]
        return len(recent) / 60.0

    @property
    def trade_rate(self) -> float:
        """Trades per minute over last 5 minutes."""
        now = time.time()
        recent = [t for t in self.trade_timestamps if now - t <= 300]
        return len(recent) / 5.0

    @property
    def depth_imbalance(self) -> float:
        """Depth imbalance: -1 (all no) to +1 (all yes). 0 = balanced."""
        total = self.yes_depth + self.no_depth
        if total == 0:
            return 0.0
        return (self.yes_depth - self.no_depth) / total

    def classify(self, config: dict) -> MarketRegime:
        """Classify current regime based on features."""
        # Pre-settlement: price near extremes
        if self.last_price is not None:
            threshold = config.get("pre_settle_price_threshold", 5)
            if self.last_price <= threshold or self.last_price >= (100 - threshold):
                if self.trade_rate > config.get("pre_settle_trade_rate", 2):
                    return MarketRegime.PRE_SETTLEMENT

        # Dead: no activity
        if (
            self.trade_rate < config.get("dead_trade_rate", 0.2)
            and self.message_rate < config.get("dead_message_rate", 0.1)
        ):
            return MarketRegime.DEAD

        # Informed: asymmetric depth drain + burst activity
        if (
            abs(self.depth_imbalance) > config.get("informed_imbalance", 0.6)
            and self.trade_rate > config.get("informed_trade_rate", 5)
        ):
            return MarketRegime.INFORMED

        # Active: steady flow
        if self.trade_rate > config.get("active_trade_rate", 2) and self.message_rate > 0.5:
            return MarketRegime.ACTIVE

        # Quiet: default
        return MarketRegime.QUIET


class RegimeDetector(BaseSignalProcessor):
    """
    Classifies each market into a microstructure regime.

    Consumes: kalshi:orderbook:deltas, kalshi:trades, kalshi:ticker_v2
    Publishes: kalshi:signals:regime
    Also updates: Redis cache key state:regime:{ticker}
    """

    PROCESSOR_NAME = "regime"
    INPUT_STREAMS = [STREAM_ORDERBOOK_DELTAS, STREAM_TRADES, STREAM_TICKER_V2]
    OUTPUT_STREAM = "kalshi:signals:regime"

    def __init__(
        self,
        redis_consumer: RedisStreamConsumer,
        signal_publisher: SignalPublisher,
        config: dict,
        redis: aioredis.Redis | None = None,
    ) -> None:
        super().__init__(redis_consumer, signal_publisher, config)
        self._redis = redis
        self.market_state: dict[str, RegimeMarketState] = {}
        self.last_regime_publish: dict[str, float] = {}

    def _get_or_create_state(self, ticker: str) -> RegimeMarketState:
        if ticker not in self.market_state:
            self.market_state[ticker] = RegimeMarketState()
        return self.market_state[ticker]

    async def process_message(self, stream: str, message: dict) -> list[Signal]:
        if stream == STREAM_ORDERBOOK_DELTAS:
            return await self._process_orderbook_delta(message)
        elif stream == STREAM_TRADES:
            return await self._process_trade(message)
        elif stream == STREAM_TICKER_V2:
            return await self._process_ticker(message)
        return []

    async def _process_orderbook_delta(self, message: dict) -> list[Signal]:
        delta = OrderbookDelta.model_validate(message)
        state = self._get_or_create_state(delta.market_ticker)
        state.update_from_delta(delta)
        return await self._maybe_emit_regime(delta.market_ticker)

    async def _process_trade(self, message: dict) -> list[Signal]:
        trade = KalshiTrade.model_validate(message)
        state = self._get_or_create_state(trade.market_ticker)
        state.update_from_trade(trade)
        return await self._maybe_emit_regime(trade.market_ticker)

    async def _process_ticker(self, message: dict) -> list[Signal]:
        ticker = KalshiTickerV2.model_validate(message)
        state = self._get_or_create_state(ticker.market_ticker)
        state.update_from_ticker(ticker)
        return await self._maybe_emit_regime(ticker.market_ticker)

    async def _maybe_emit_regime(self, ticker: str) -> list[Signal]:
        """Rate-limited regime publishing."""
        now = time.time()
        last = self.last_regime_publish.get(ticker, 0)
        publish_interval = self.config.get("publish_interval", 30)
        if now - last < publish_interval:
            return []

        state = self.market_state[ticker]
        regime = state.classify(self.config)

        # Always update Redis cache
        await self._update_redis_regime(ticker, regime, state)
        self.last_regime_publish[ticker] = now

        # Only emit signal if regime CHANGED
        if regime != state.previous_regime:
            old_regime = state.previous_regime
            state.previous_regime = regime
            state.regime_history.append((now, regime))
            return [self._create_regime_signal(ticker, regime, old_regime, state)]

        return []

    async def _update_redis_regime(
        self, ticker: str, regime: MarketRegime, state: RegimeMarketState
    ) -> None:
        """Update Redis cache with current regime for fast lookups."""
        if self._redis is None:
            return
        key = KEY_REGIME.format(ticker=ticker)
        data = {
            "regime": regime.value,
            "depth_imbalance": round(state.depth_imbalance, 4),
            "trade_rate": round(state.trade_rate, 2),
            "message_rate": round(state.message_rate, 2),
            "last_price": state.last_price,
            "yes_depth": state.yes_depth,
            "no_depth": state.no_depth,
            "ts": time.time(),
        }
        await self._redis.set(key, orjson.dumps(data).decode(), ex=120)

    def _create_regime_signal(
        self,
        ticker: str,
        regime: MarketRegime,
        old_regime: MarketRegime,
        state: RegimeMarketState,
    ) -> Signal:
        return Signal(
            signal_type="regime_change",
            market_ticker=ticker,
            direction=SignalDirection.NEUTRAL,
            strength=0.5,
            confidence=0.8,
            urgency=(
                SignalUrgency.IMMEDIATE
                if regime == MarketRegime.INFORMED
                else SignalUrgency.BACKGROUND
            ),
            metadata={
                "new_regime": regime.value,
                "old_regime": old_regime.value,
                "trade_rate": round(state.trade_rate, 2),
                "message_rate": round(state.message_rate, 2),
                "depth_imbalance": round(state.depth_imbalance, 4),
                "last_price": state.last_price,
            },
        )


async def main() -> None:
    """Entry point for the regime detector process."""
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

    processor = RegimeDetector(consumer, publisher, REGIME_CONFIG, redis=redis)
    await processor.run()


if __name__ == "__main__":
    asyncio.run(main())
