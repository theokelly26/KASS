"""Cross-Market Propagation Engine — detects repricing opportunities across related markets.

When a signal fires on one market in an event/series, checks whether related
markets have repriced accordingly. If they haven't, that's the opportunity.
"""

from __future__ import annotations

import asyncio
import re
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

# Patterns to extract numeric thresholds from market titles
_ABOVE_RE = re.compile(r"(?:\$?([\d,]+\.?\d*)\s+or\s+(?:above|more|higher))|(?:(?:above|over|more than|at least|≥|>=)\s*\$?([\d,]+\.?\d*))", re.IGNORECASE)
_BELOW_RE = re.compile(r"(?:\$?([\d,]+\.?\d*)\s+or\s+(?:below|less|lower|fewer))|(?:(?:below|under|less than|at most|≤|<=)\s*\$?([\d,]+\.?\d*))", re.IGNORECASE)
_BETWEEN_RE = re.compile(r"(?:between)\s*\$?([\d,]+\.?\d*)%?\s*(?:and|to|-)\s*\$?([\d,]+\.?\d*)%?", re.IGNORECASE)


def _parse_threshold(title: str) -> tuple[str, float] | None:
    """Parse a threshold from a market title/subtitle. Returns (type, value) or None."""
    m = _ABOVE_RE.search(title)
    if m:
        val = m.group(1) or m.group(2)
        return ("above", float(val.replace(",", "")))
    m = _BELOW_RE.search(title)
    if m:
        val = m.group(1) or m.group(2)
        return ("below", float(val.replace(",", "")))
    m = _BETWEEN_RE.search(title)
    if m:
        midpoint = (float(m.group(1).replace(",", "")) + float(m.group(2).replace(",", ""))) / 2
        return ("between", midpoint)
    return None

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
        # Cache for market titles per event {event_ticker: {ticker: title}}
        self._event_titles_cache: dict[str, dict[str, str]] = {}
        # Cache for parsed thresholds {ticker: (type, value) | None}
        self._threshold_cache: dict[str, tuple[str, float] | None] = {}

    async def process_message(self, stream: str, message: dict) -> list[Signal]:
        signals: list[Signal] = []

        if stream == STREAM_TICKER_V2:
            ticker = KalshiTickerV2.model_validate(message)
            # Populate event_ticker cache on first sight of a market
            if ticker.market_ticker not in self._event_ticker_cache:
                await self._populate_event_ticker(ticker.market_ticker)
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
                signal = Signal.model_validate(message)
                if signal.direction != SignalDirection.NEUTRAL:
                    if signal.strength >= self.config.get("min_source_strength", 0.5):
                        prop_signals = await self._check_signal_propagation(signal)
                        signals.extend(prop_signals)
            except Exception:
                self.logger.debug("signal_parse_skip", stream=stream)

        return signals

    async def _populate_event_ticker(self, market_ticker: str) -> None:
        """Look up event_ticker from DB and cache it."""
        if self.series_mapper is None:
            self._event_ticker_cache[market_ticker] = None
            return
        try:
            from src.persistence.db import get_connection

            async with get_connection(self.series_mapper._pg_config) as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT event_ticker FROM markets WHERE ticker = %s",
                        (market_ticker,),
                    )
                    row = await cur.fetchone()
                    self._event_ticker_cache[market_ticker] = row[0] if row else None
        except Exception:
            self._event_ticker_cache[market_ticker] = None

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
                # Ensure we have titles cached for bracket detection
                await self._ensure_titles_cached(moved_ticker)
                await self._ensure_titles_cached(related_ticker)
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

    async def _ensure_titles_cached(self, ticker: str) -> None:
        """Load market titles for the event containing ticker."""
        event_ticker = self._event_ticker_cache.get(ticker)
        if not event_ticker or event_ticker in self._event_titles_cache:
            return
        if self.series_mapper is None:
            return
        try:
            titles = await self.series_mapper.get_market_titles(event_ticker)
            self._event_titles_cache[event_ticker] = titles
            for t, (title, subtitle) in titles.items():
                if t not in self._threshold_cache:
                    # Try subtitle first (Kalshi puts thresholds there for brackets)
                    # then fall back to title
                    parsed = None
                    if subtitle:
                        parsed = _parse_threshold(subtitle)
                    if parsed is None:
                        parsed = _parse_threshold(title)
                    self._threshold_cache[t] = parsed
        except Exception:
            self.logger.debug("title_cache_error", event_ticker=event_ticker)

    def _infer_expected_direction(
        self, source: str, target: str, source_direction: str
    ) -> SignalDirection | None:
        """
        Given that source moved in source_direction, what should target do?

        For bracket markets (above/below thresholds), uses threshold ordering
        to determine correlation. For non-bracket markets, returns None to
        avoid emitting anti-predictive signals.
        """
        source_thresh = self._threshold_cache.get(source)
        target_thresh = self._threshold_cache.get(target)

        # Both must have parseable thresholds, and same type
        if source_thresh is None or target_thresh is None:
            return None
        if source_thresh[0] != target_thresh[0]:
            return None

        s_val = source_thresh[1]
        t_val = target_thresh[1]

        if s_val == t_val:
            return None  # Same threshold — can't infer

        thresh_type = source_thresh[0]

        if thresh_type == "above":
            # "above X" markets: if source (above 60k) goes up and target is above 70k,
            # that's positively correlated (both become more likely as underlying rises).
            # Higher threshold = more sensitive to upside.
            # Source up + target has higher threshold → target also up (but less certain)
            # Source up + target has lower threshold → target also up (even more certain)
            if source_direction == "up":
                return SignalDirection.BUY_YES
            else:
                return SignalDirection.BUY_NO
        elif thresh_type == "below":
            # "below X" markets: inversely related to underlying.
            # If source (below 60k) goes up → underlying dropping.
            # Target (below 70k) should also go up.
            if source_direction == "up":
                return SignalDirection.BUY_YES
            else:
                return SignalDirection.BUY_NO
        elif thresh_type == "between":
            # Between/range brackets are NOT simply correlated.
            # Skip these — direction depends on which direction the underlying moved.
            return None

        return None

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
