"""OI Divergence Detector — tracks open interest vs price divergences.

Detects when OI moves one way but price moves the other, signaling
hidden positioning building beneath the surface.
"""

from __future__ import annotations

import asyncio
from collections import deque

import structlog

from src.cache.redis_client import get_redis
from src.cache.streams import STREAM_TICKER_V2, RedisStreamConsumer
from src.config import get_config
from src.models import KalshiTickerV2
from src.signals.base import BaseSignalProcessor
from src.signals.config import OI_DIVERGENCE_CONFIG
from src.signals.models import Signal, SignalDirection, SignalUrgency
from src.signals.streams import SignalPublisher

logger = structlog.get_logger(__name__)

# Regime → signal direction mapping
REGIME_TO_SIGNAL = {
    "new_longs": SignalDirection.BUY_YES,
    "new_shorts": SignalDirection.BUY_NO,
    "short_covering": SignalDirection.BUY_YES,
    "long_liquidation": SignalDirection.BUY_NO,
}

# Conviction regimes get higher confidence
REGIME_CONFIDENCE = {
    "new_longs": 0.75,
    "new_shorts": 0.75,
    "short_covering": 0.45,
    "long_liquidation": 0.45,
}


class OIMarketState:
    """Per-market state for OI divergence analysis."""

    def __init__(self, window_size: int = 50) -> None:
        self.window_size = window_size

        # Rolling windows
        self.prices: deque[int] = deque(maxlen=window_size)
        self.oi_deltas: deque[float] = deque(maxlen=window_size)
        self.dollar_oi_deltas: deque[int] = deque(maxlen=window_size)
        self.timestamps: deque[int] = deque(maxlen=window_size)

        # Running totals
        self.cumulative_oi_delta: float = 0.0
        self.observation_count: int = 0

        # Historical OI velocity for z-score
        self.oi_velocity_history: deque[float] = deque(maxlen=200)

    def update(self, ticker: KalshiTickerV2) -> None:
        if ticker.price is not None:
            self.prices.append(ticker.price)
        if ticker.open_interest_delta is not None:
            oi_delta = float(ticker.open_interest_delta)
            self.oi_deltas.append(oi_delta)
            self.cumulative_oi_delta += oi_delta
        if ticker.dollar_open_interest_delta is not None:
            self.dollar_oi_deltas.append(ticker.dollar_open_interest_delta)
        self.timestamps.append(ticker.ts)
        self.observation_count += 1

    def classify_regime(self) -> str:
        """Classify the current OI/price regime using 4 classic regimes."""
        if len(self.prices) < 5 or len(self.oi_deltas) < 5:
            return "insufficient_data"

        # Price direction: compare recent mean to earlier mean
        mid = len(self.prices) // 2
        recent_prices = list(self.prices)[mid:]
        earlier_prices = list(self.prices)[:mid]
        price_rising = (sum(recent_prices) / len(recent_prices)) > (
            sum(earlier_prices) / len(earlier_prices)
        )

        # OI direction: net OI change over recent window
        recent_oi = list(self.oi_deltas)[-10:]
        oi_net = sum(recent_oi)
        oi_rising = oi_net > 0

        if oi_rising and price_rising:
            return "new_longs"
        elif oi_rising and not price_rising:
            return "new_shorts"
        elif not oi_rising and price_rising:
            return "short_covering"
        else:
            return "long_liquidation"

    @property
    def oi_velocity(self) -> float:
        """OI change rate: net OI delta per observation in recent window."""
        if len(self.oi_deltas) < 2:
            return 0.0
        recent = list(self.oi_deltas)[-10:]
        return sum(recent) / len(recent)

    @property
    def oi_velocity_zscore(self) -> float:
        """How unusual is the current OI velocity vs history."""
        current = self.oi_velocity
        if len(self.oi_velocity_history) < 10:
            self.oi_velocity_history.append(abs(current))
            return 0.0

        self.oi_velocity_history.append(abs(current))
        mean = sum(self.oi_velocity_history) / len(self.oi_velocity_history)
        variance = sum(
            (x - mean) ** 2 for x in self.oi_velocity_history
        ) / len(self.oi_velocity_history)
        std = variance**0.5

        if std < 0.001:
            return 0.0
        return (abs(current) - mean) / std

    @property
    def dollar_oi_confirms(self) -> bool:
        """Does dollar-weighted OI confirm the direction of contract-count OI."""
        if not self.dollar_oi_deltas or not self.oi_deltas:
            return False
        recent_oi = sum(list(self.oi_deltas)[-5:])
        recent_dollar_oi = sum(list(self.dollar_oi_deltas)[-5:])
        return (recent_oi > 0 and recent_dollar_oi > 0) or (
            recent_oi < 0 and recent_dollar_oi < 0
        )

    @property
    def last_price(self) -> int | None:
        return self.prices[-1] if self.prices else None


class OIDivergenceDetector(BaseSignalProcessor):
    """
    Detects divergences between open interest and price movements.

    Consumes: kalshi:ticker_v2
    Publishes: kalshi:signals:oi_divergence
    """

    PROCESSOR_NAME = "oi_divergence"
    INPUT_STREAMS = [STREAM_TICKER_V2]
    OUTPUT_STREAM = "kalshi:signals:oi_divergence"

    def __init__(
        self,
        redis_consumer: RedisStreamConsumer,
        signal_publisher: SignalPublisher,
        config: dict,
    ) -> None:
        super().__init__(redis_consumer, signal_publisher, config)
        self.market_state: dict[str, OIMarketState] = {}

    def _get_or_create_state(self, ticker: str) -> OIMarketState:
        if ticker not in self.market_state:
            self.market_state[ticker] = OIMarketState(
                window_size=self.config["window_size"]
            )
        return self.market_state[ticker]

    async def process_message(self, stream: str, message: dict) -> list[Signal]:
        ticker = KalshiTickerV2.model_validate(message)

        # Skip updates without OI or price data
        if ticker.open_interest_delta is None and ticker.price is None:
            return []

        state = self._get_or_create_state(ticker.market_ticker)
        state.update(ticker)

        # Filter extreme prices (no edge)
        if state.last_price is not None:
            if (
                state.last_price < self.config["min_price_for_signal"]
                or state.last_price > self.config["max_price_for_signal"]
            ):
                return []

        # Need enough data points
        if state.observation_count < self.config["min_observations"]:
            return []

        regime = state.classify_regime()
        if regime == "insufficient_data":
            return []

        signals: list[Signal] = []

        # Check if OI velocity is significant
        zscore = state.oi_velocity_zscore
        if zscore > self.config["oi_zscore_threshold"]:
            signal = self._create_divergence_signal(
                ticker.market_ticker, regime, state, zscore
            )
            if signal:
                signals.append(signal)

        return signals

    def _create_divergence_signal(
        self,
        ticker: str,
        regime: str,
        state: OIMarketState,
        zscore: float,
    ) -> Signal | None:
        direction = REGIME_TO_SIGNAL.get(regime)
        if direction is None:
            return None

        base_confidence = REGIME_CONFIDENCE.get(regime, 0.5)
        confidence = base_confidence

        # Boost confidence if dollar OI confirms
        if state.dollar_oi_confirms:
            confidence = min(1.0, confidence + self.config["dollar_oi_confirmation_boost"])

        return Signal(
            signal_type="oi_divergence",
            market_ticker=ticker,
            direction=direction,
            strength=min(1.0, zscore / 3.0),  # Normalize z-score to 0-1
            confidence=confidence,
            urgency=SignalUrgency.WATCH,
            metadata={
                "regime": regime,
                "oi_velocity": round(state.oi_velocity, 4),
                "oi_velocity_zscore": round(zscore, 4),
                "cumulative_oi_delta": round(state.cumulative_oi_delta, 2),
                "dollar_oi_confirms": state.dollar_oi_confirms,
                "observation_count": state.observation_count,
                "last_price": state.last_price,
            },
        )


async def main() -> None:
    """Entry point for the OI divergence processor."""
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

    processor = OIDivergenceDetector(consumer, publisher, OI_DIVERGENCE_CONFIG)
    await processor.run()


if __name__ == "__main__":
    asyncio.run(main())
