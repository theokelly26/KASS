"""Flow Toxicity Classifier — VPIN-adapted informed flow detection for prediction markets.

Detects informed trading flow using volume-synchronized trade analysis.
Maintains per-market state with volume buckets, burst detection, and
large trade anomaly detection.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque

import structlog

from src.cache.redis_client import get_redis
from src.cache.streams import STREAM_TRADES, RedisStreamConsumer
from src.config import get_config
from src.models import KalshiTrade
from src.signals.base import BaseSignalProcessor
from src.signals.config import FLOW_TOXICITY_CONFIG
from src.signals.models import Signal, SignalDirection, SignalUrgency
from src.signals.streams import SignalPublisher

logger = structlog.get_logger(__name__)


class MarketFlowState:
    """Per-market state for flow analysis."""

    def __init__(self, bucket_size: int = 50, window_size: int = 20) -> None:
        self.bucket_size = bucket_size
        self.window_size = window_size

        # Current bucket
        self.current_bucket_volume = 0
        self.current_bucket_buy_volume = 0

        # Rolling window of completed buckets
        self.bucket_vpins: deque[float] = deque(maxlen=window_size)

        # Trade arrival tracking
        self.trade_timestamps: deque[float] = deque(maxlen=100)
        self.trade_sizes: deque[int] = deque(maxlen=200)

        # Running statistics
        self.total_volume = 0
        self.total_trades = 0

    def add_trade(self, trade: KalshiTrade) -> None:
        """Add a trade to the current bucket."""
        self.current_bucket_volume += trade.count
        if trade.taker_side == "yes":
            self.current_bucket_buy_volume += trade.count
        self.trade_timestamps.append(trade.ts)
        self.trade_sizes.append(trade.count)
        self.total_volume += trade.count
        self.total_trades += 1

    def current_bucket_full(self) -> bool:
        return self.current_bucket_volume >= self.bucket_size

    def compute_vpin(self) -> float:
        """
        VPIN for current bucket.
        VPIN = |buy_ratio - 0.5| * 2, normalized to [0, 1]
        0 = perfectly balanced, 1 = completely one-sided.
        """
        if self.current_bucket_volume == 0:
            return 0.0
        buy_ratio = self.current_bucket_buy_volume / self.current_bucket_volume
        return abs(buy_ratio - 0.5) * 2.0

    def advance_bucket(self) -> None:
        """Close current bucket, start new one."""
        self.bucket_vpins.append(self.compute_vpin())
        self.current_bucket_volume = 0
        self.current_bucket_buy_volume = 0

    @property
    def rolling_vpin(self) -> float:
        """Average VPIN over the rolling window."""
        if not self.bucket_vpins:
            return 0.0
        return sum(self.bucket_vpins) / len(self.bucket_vpins)

    @property
    def mean_trade_size(self) -> float:
        if not self.trade_sizes:
            return 0.0
        return sum(self.trade_sizes) / len(self.trade_sizes)

    def detect_burst(
        self, window_seconds: float = 5.0, min_trades: int = 5
    ) -> bool:
        """Detect burst of trades in a short time window."""
        if len(self.trade_timestamps) < min_trades:
            return False
        now = self.trade_timestamps[-1]
        recent = [t for t in self.trade_timestamps if now - t <= window_seconds]
        return len(recent) >= min_trades

    @property
    def dominant_side(self) -> str:
        """Which side is the flow predominantly on. Requires 60%+ imbalance."""
        if self.current_bucket_volume == 0:
            return "neutral"
        buy_ratio = self.current_bucket_buy_volume / self.current_bucket_volume
        if buy_ratio > 0.6:
            return "yes"
        elif buy_ratio < 0.4:
            return "no"
        return "neutral"

    @property
    def inter_arrival_rate(self) -> float:
        """Trades per second based on recent timestamps."""
        if len(self.trade_timestamps) < 2:
            return 0.0
        ts_list = list(self.trade_timestamps)
        span = ts_list[-1] - ts_list[0]
        if span <= 0:
            return 0.0
        return len(ts_list) / span


class FlowToxicityClassifier(BaseSignalProcessor):
    """
    Detects informed flow using volume-synchronized trade analysis (VPIN).

    Consumes: kalshi:trades
    Publishes: kalshi:signals:flow_toxicity
    """

    PROCESSOR_NAME = "flow_toxicity"
    INPUT_STREAMS = [STREAM_TRADES]
    OUTPUT_STREAM = "kalshi:signals:flow_toxicity"

    def __init__(
        self,
        redis_consumer: RedisStreamConsumer,
        signal_publisher: SignalPublisher,
        config: dict,
    ) -> None:
        super().__init__(redis_consumer, signal_publisher, config)
        self.market_state: dict[str, MarketFlowState] = {}

    def _get_or_create_state(self, ticker: str) -> MarketFlowState:
        if ticker not in self.market_state:
            self.market_state[ticker] = MarketFlowState(
                bucket_size=self.config["bucket_size"],
                window_size=self.config["window_size"],
            )
        return self.market_state[ticker]

    async def process_message(self, stream: str, message: dict) -> list[Signal]:
        """Process a trade and update flow state for that market."""
        trade = KalshiTrade.model_validate(message)
        state = self._get_or_create_state(trade.market_ticker)

        # Skip markets with insufficient volume
        if state.total_volume < self.config["min_market_volume"] and state.total_trades > 10:
            return []

        state.add_trade(trade)
        signals: list[Signal] = []

        # Check if volume bucket is full
        if state.current_bucket_full():
            vpin = state.compute_vpin()
            state.advance_bucket()

            # High VPIN signal
            if vpin > self.config["vpin_threshold"]:
                signals.append(
                    self._create_toxicity_signal(trade.market_ticker, vpin, state)
                )

            # Rolling VPIN signal
            if state.rolling_vpin > self.config["rolling_vpin_threshold"]:
                if len(state.bucket_vpins) >= 5:  # Need enough buckets
                    signals.append(
                        self._create_rolling_toxicity_signal(
                            trade.market_ticker, state
                        )
                    )

        # Burst detection
        if state.detect_burst(
            window_seconds=self.config["burst_window_seconds"],
            min_trades=self.config["burst_min_trades"],
        ):
            signals.append(
                self._create_burst_signal(trade.market_ticker, state)
            )

        # Large trade anomaly
        if (
            state.mean_trade_size > 0
            and trade.count > state.mean_trade_size * self.config["size_multiplier"]
        ):
            signals.append(
                self._create_large_trade_signal(trade.market_ticker, trade, state)
            )

        return signals

    def _create_toxicity_signal(
        self, ticker: str, vpin: float, state: MarketFlowState
    ) -> Signal:
        direction = (
            SignalDirection.BUY_YES
            if state.dominant_side == "yes"
            else SignalDirection.BUY_NO
            if state.dominant_side == "no"
            else SignalDirection.NEUTRAL
        )
        return Signal(
            signal_type="flow_toxicity",
            market_ticker=ticker,
            direction=direction,
            strength=min(1.0, vpin),
            confidence=min(1.0, 0.5 + (len(state.bucket_vpins) / state.window_size) * 0.3),
            urgency=SignalUrgency.IMMEDIATE if vpin > 0.85 else SignalUrgency.WATCH,
            metadata={
                "vpin": round(vpin, 4),
                "rolling_vpin": round(state.rolling_vpin, 4),
                "bucket_count": len(state.bucket_vpins),
                "dominant_side": state.dominant_side,
                "total_volume": state.total_volume,
            },
        )

    def _create_rolling_toxicity_signal(
        self, ticker: str, state: MarketFlowState
    ) -> Signal:
        direction = (
            SignalDirection.BUY_YES
            if state.dominant_side == "yes"
            else SignalDirection.BUY_NO
            if state.dominant_side == "no"
            else SignalDirection.NEUTRAL
        )
        return Signal(
            signal_type="flow_toxicity",
            market_ticker=ticker,
            direction=direction,
            strength=min(1.0, state.rolling_vpin),
            confidence=0.7,
            urgency=SignalUrgency.WATCH,
            metadata={
                "rolling_vpin": round(state.rolling_vpin, 4),
                "bucket_count": len(state.bucket_vpins),
                "dominant_side": state.dominant_side,
                "pattern": "sustained_toxicity",
            },
        )

    def _create_burst_signal(self, ticker: str, state: MarketFlowState) -> Signal:
        return Signal(
            signal_type="flow_burst",
            market_ticker=ticker,
            direction=(
                SignalDirection.BUY_YES
                if state.dominant_side == "yes"
                else SignalDirection.BUY_NO
                if state.dominant_side == "no"
                else SignalDirection.NEUTRAL
            ),
            strength=min(1.0, state.inter_arrival_rate / 10.0),
            confidence=min(0.8, 0.3 + (state.inter_arrival_rate / 20.0)),
            urgency=SignalUrgency.IMMEDIATE,
            metadata={
                "inter_arrival_rate": round(state.inter_arrival_rate, 2),
                "dominant_side": state.dominant_side,
                "trade_burst": True,
            },
        )

    def _create_large_trade_signal(
        self, ticker: str, trade: KalshiTrade, state: MarketFlowState
    ) -> Signal:
        size_ratio = trade.count / state.mean_trade_size if state.mean_trade_size > 0 else 0
        return Signal(
            signal_type="flow_large_trade",
            market_ticker=ticker,
            direction=(
                SignalDirection.BUY_YES
                if trade.taker_side == "yes"
                else SignalDirection.BUY_NO
            ),
            strength=min(1.0, trade.count / (state.mean_trade_size * self.config["size_multiplier"] * 2)),
            confidence=min(0.85, 0.4 + (size_ratio / (self.config["size_multiplier"] * 4))),
            urgency=SignalUrgency.WATCH,
            metadata={
                "trade_size": trade.count,
                "mean_trade_size": round(state.mean_trade_size, 2),
                "size_ratio": round(size_ratio, 2),
                "taker_side": trade.taker_side,
            },
        )


async def main() -> None:
    """Entry point for the flow toxicity processor."""
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

    processor = FlowToxicityClassifier(consumer, publisher, FLOW_TOXICITY_CONFIG)
    await processor.run()


if __name__ == "__main__":
    asyncio.run(main())
