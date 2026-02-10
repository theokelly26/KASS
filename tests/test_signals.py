"""Unit tests for Phase 2 signal processors."""

from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.signals.models import (
    CompositeSignal,
    MarketRegime,
    Signal,
    SignalDirection,
    SignalUrgency,
)
from src.signals.config import (
    FLOW_TOXICITY_CONFIG,
    OI_DIVERGENCE_CONFIG,
    REGIME_CONFIG,
    AGGREGATOR_CONFIG,
)
from src.signals.flow.toxicity import FlowToxicityClassifier, MarketFlowState
from src.signals.flow.oi_divergence import OIDivergenceDetector, OIMarketState
from src.signals.microstructure.regime import RegimeDetector, RegimeMarketState


# ── Signal model tests ──────────────────────────────────────────


class TestSignalModel:
    def test_signal_creation(self) -> None:
        signal = Signal(
            signal_type="test",
            market_ticker="TEST-MKT",
            direction=SignalDirection.BUY_YES,
            strength=0.8,
            confidence=0.7,
            urgency=SignalUrgency.WATCH,
        )
        assert signal.signal_id  # UUID generated
        assert signal.strength == 0.8
        assert not signal.is_expired()

    def test_signal_expiration(self) -> None:
        signal = Signal(
            signal_type="test",
            market_ticker="TEST-MKT",
            direction=SignalDirection.NEUTRAL,
            strength=0.5,
            confidence=0.5,
            urgency=SignalUrgency.BACKGROUND,
            ts=datetime.now(tz=timezone.utc) - timedelta(seconds=400),
            ttl_seconds=300,
        )
        assert signal.is_expired()

    def test_signal_not_expired(self) -> None:
        signal = Signal(
            signal_type="test",
            market_ticker="TEST-MKT",
            direction=SignalDirection.BUY_NO,
            strength=0.5,
            confidence=0.5,
            urgency=SignalUrgency.IMMEDIATE,
            ttl_seconds=300,
        )
        assert not signal.is_expired()

    def test_signal_serialization(self) -> None:
        signal = Signal(
            signal_type="test",
            market_ticker="TEST-MKT",
            direction=SignalDirection.BUY_YES,
            strength=0.8,
            confidence=0.7,
            urgency=SignalUrgency.WATCH,
        )
        payload = signal.to_redis_payload()
        restored = Signal.model_validate_json(payload)
        assert restored.market_ticker == "TEST-MKT"
        assert restored.strength == 0.8

    def test_composite_signal(self) -> None:
        signal = Signal(
            signal_type="test",
            market_ticker="TEST-MKT",
            direction=SignalDirection.BUY_YES,
            strength=0.8,
            confidence=0.7,
            urgency=SignalUrgency.WATCH,
        )
        composite = CompositeSignal(
            market_ticker="TEST-MKT",
            direction=SignalDirection.BUY_YES,
            composite_score=0.65,
            active_signals=[signal],
            regime=MarketRegime.ACTIVE,
        )
        assert composite.composite_score == 0.65
        assert len(composite.active_signals) == 1


# ── Flow Toxicity tests ─────────────────────────────────────────


class TestMarketFlowState:
    def test_balanced_trades_low_vpin(self) -> None:
        """100 balanced trades should produce VPIN near 0."""
        state = MarketFlowState(bucket_size=50, window_size=20)
        from src.models import KalshiTrade

        for i in range(100):
            trade = KalshiTrade(
                trade_id=f"t{i}",
                market_ticker="TEST",
                yes_price=50,
                yes_price_dollars="0.500",
                no_price=50,
                no_price_dollars="0.500",
                count=1,
                count_fp="1.00",
                taker_side="yes" if i % 2 == 0 else "no",
                ts=1700000000 + i,
            )
            state.add_trade(trade)
            if state.current_bucket_full():
                vpin = state.compute_vpin()
                state.advance_bucket()
                assert vpin < 0.1  # Should be near 0 for balanced flow

    def test_onesided_trades_high_vpin(self) -> None:
        """100 all-yes trades should produce VPIN near 1.0."""
        state = MarketFlowState(bucket_size=50, window_size=20)
        from src.models import KalshiTrade

        for i in range(100):
            trade = KalshiTrade(
                trade_id=f"t{i}",
                market_ticker="TEST",
                yes_price=50,
                yes_price_dollars="0.500",
                no_price=50,
                no_price_dollars="0.500",
                count=1,
                count_fp="1.00",
                taker_side="yes",
                ts=1700000000 + i,
            )
            state.add_trade(trade)
            if state.current_bucket_full():
                vpin = state.compute_vpin()
                state.advance_bucket()
                assert vpin > 0.9  # Should be near 1.0

    def test_burst_detection(self) -> None:
        """10 trades in quick succession should trigger burst."""
        state = MarketFlowState()
        from src.models import KalshiTrade

        base_ts = 1700000000
        for i in range(10):
            trade = KalshiTrade(
                trade_id=f"t{i}",
                market_ticker="TEST",
                yes_price=50,
                yes_price_dollars="0.500",
                no_price=50,
                no_price_dollars="0.500",
                count=1,
                count_fp="1.00",
                taker_side="yes",
                ts=base_ts + i,  # 1 sec apart, 10 trades in 9 seconds
            )
            state.add_trade(trade)

        assert state.detect_burst(window_seconds=15.0, min_trades=5)

    def test_dominant_side(self) -> None:
        state = MarketFlowState()
        from src.models import KalshiTrade

        # 7 yes, 3 no → yes dominant
        for i in range(10):
            trade = KalshiTrade(
                trade_id=f"t{i}",
                market_ticker="TEST",
                yes_price=50,
                yes_price_dollars="0.500",
                no_price=50,
                no_price_dollars="0.500",
                count=1,
                count_fp="1.00",
                taker_side="yes" if i < 7 else "no",
                ts=1700000000 + i,
            )
            state.add_trade(trade)

        assert state.dominant_side == "yes"


# ── OI Divergence tests ─────────────────────────────────────────


class TestOIMarketState:
    def test_new_longs_regime(self) -> None:
        """Rising OI + rising price = new_longs."""
        state = OIMarketState(window_size=50)
        from src.models import KalshiTickerV2

        # Simulate rising price + rising OI
        for i in range(20):
            ticker = KalshiTickerV2(
                market_ticker="TEST",
                market_id="m1",
                price=40 + i,  # Rising
                open_interest_delta=5,  # Always positive
                open_interest_delta_fp="5.00",
                ts=1700000000 + i * 60,
            )
            state.update(ticker)

        regime = state.classify_regime()
        assert regime == "new_longs"

    def test_new_shorts_regime(self) -> None:
        """Rising OI + falling price = new_shorts."""
        state = OIMarketState(window_size=50)
        from src.models import KalshiTickerV2

        for i in range(20):
            ticker = KalshiTickerV2(
                market_ticker="TEST",
                market_id="m1",
                price=60 - i,  # Falling
                open_interest_delta=5,  # Always positive
                open_interest_delta_fp="5.00",
                ts=1700000000 + i * 60,
            )
            state.update(ticker)

        regime = state.classify_regime()
        assert regime == "new_shorts"

    def test_insufficient_data(self) -> None:
        state = OIMarketState()
        from src.models import KalshiTickerV2

        ticker = KalshiTickerV2(
            market_ticker="TEST",
            market_id="m1",
            price=50,
            ts=1700000000,
        )
        state.update(ticker)
        assert state.classify_regime() == "insufficient_data"

    def test_oi_velocity(self) -> None:
        state = OIMarketState()
        from src.models import KalshiTickerV2

        for i in range(15):
            ticker = KalshiTickerV2(
                market_ticker="TEST",
                market_id="m1",
                open_interest_delta=10,
                open_interest_delta_fp="10.00",
                ts=1700000000 + i,
            )
            state.update(ticker)

        assert state.oi_velocity > 0


# ── Regime Detector tests ────────────────────────────────────────


class TestRegimeMarketState:
    def test_dead_market(self) -> None:
        """No activity → DEAD regime."""
        state = RegimeMarketState()
        regime = state.classify(REGIME_CONFIG)
        assert regime == MarketRegime.DEAD

    def test_pre_settlement(self) -> None:
        """Price near 95+ with trading → PRE_SETTLEMENT."""
        state = RegimeMarketState()
        state.last_price = 97
        state.prices.append(97)
        # Simulate trades in last 5 minutes
        now = time.time()
        for i in range(15):
            state.trade_timestamps.append(now - i * 10)
        regime = state.classify(REGIME_CONFIG)
        assert regime == MarketRegime.PRE_SETTLEMENT

    def test_informed_regime(self) -> None:
        """High depth imbalance + high trade rate → INFORMED."""
        state = RegimeMarketState()
        state.yes_depth = 1000
        state.no_depth = 100  # Big imbalance
        now = time.time()
        for i in range(30):
            state.trade_timestamps.append(now - i * 5)
        state.last_price = 50
        regime = state.classify(REGIME_CONFIG)
        assert regime == MarketRegime.INFORMED

    def test_active_regime(self) -> None:
        """Steady trade flow → ACTIVE."""
        state = RegimeMarketState()
        state.yes_depth = 500
        state.no_depth = 500
        now = time.time()
        for i in range(15):
            state.trade_timestamps.append(now - i * 10)
        # Need message_rate > 0.5: at least 31 messages within 60s
        for i in range(35):
            state.delta_timestamps.append(now - i * 1.5)
        state.last_price = 50
        regime = state.classify(REGIME_CONFIG)
        assert regime == MarketRegime.ACTIVE

    def test_depth_imbalance(self) -> None:
        state = RegimeMarketState()
        state.yes_depth = 800
        state.no_depth = 200
        assert state.depth_imbalance == pytest.approx(0.6, abs=0.01)


# ── Aggregator logic tests ──────────────────────────────────────


class TestAggregatorLogic:
    def test_positive_composite(self) -> None:
        """3 buy_yes signals → positive composite score."""
        from src.signals.aggregator.aggregator import (
            SignalAggregator,
            SIGNAL_WEIGHTS,
        )

        signals = [
            Signal(
                signal_type="flow_toxicity",
                market_ticker="TEST",
                direction=SignalDirection.BUY_YES,
                strength=0.8,
                confidence=0.7,
                urgency=SignalUrgency.WATCH,
            ),
            Signal(
                signal_type="oi_divergence",
                market_ticker="TEST",
                direction=SignalDirection.BUY_YES,
                strength=0.7,
                confidence=0.75,
                urgency=SignalUrgency.WATCH,
            ),
            Signal(
                signal_type="cross_market_propagation",
                market_ticker="TEST",
                direction=SignalDirection.BUY_YES,
                strength=0.6,
                confidence=0.65,
                urgency=SignalUrgency.IMMEDIATE,
            ),
        ]

        # Compute weighted score manually
        weighted_sum = 0.0
        total_weight = 0.0
        for s in signals:
            w = SIGNAL_WEIGHTS.get(s.signal_type, 0.1) * s.confidence
            weighted_sum += s.strength * 1.0 * w  # BUY_YES = +1
            total_weight += w
        score = weighted_sum / total_weight

        assert score > 0  # All buy_yes → positive

    def test_conflicting_signals(self) -> None:
        """Conflicting signals should partially cancel."""
        from src.signals.aggregator.aggregator import SIGNAL_WEIGHTS

        signals = [
            Signal(
                signal_type="flow_toxicity",
                market_ticker="TEST",
                direction=SignalDirection.BUY_YES,
                strength=0.8,
                confidence=0.7,
                urgency=SignalUrgency.WATCH,
            ),
            Signal(
                signal_type="oi_divergence",
                market_ticker="TEST",
                direction=SignalDirection.BUY_NO,
                strength=0.9,
                confidence=0.8,
                urgency=SignalUrgency.WATCH,
            ),
        ]

        weighted_sum = 0.0
        total_weight = 0.0
        for s in signals:
            w = SIGNAL_WEIGHTS.get(s.signal_type, 0.1) * s.confidence
            mult = 1.0 if s.direction == SignalDirection.BUY_YES else -1.0
            weighted_sum += s.strength * mult * w
            total_weight += w

        score = weighted_sum / total_weight
        # Should be negative because oi_divergence BUY_NO is stronger
        assert score < 0

    def test_expired_signals_excluded(self) -> None:
        """Expired signals should not contribute."""
        expired = Signal(
            signal_type="flow_toxicity",
            market_ticker="TEST",
            direction=SignalDirection.BUY_YES,
            strength=0.9,
            confidence=0.9,
            urgency=SignalUrgency.IMMEDIATE,
            ts=datetime.now(tz=timezone.utc) - timedelta(seconds=400),
            ttl_seconds=300,
        )
        assert expired.is_expired()

        active = Signal(
            signal_type="oi_divergence",
            market_ticker="TEST",
            direction=SignalDirection.BUY_NO,
            strength=0.5,
            confidence=0.5,
            urgency=SignalUrgency.WATCH,
        )
        assert not active.is_expired()

        # Filtering expired
        all_signals = [expired, active]
        filtered = [s for s in all_signals if not s.is_expired()]
        assert len(filtered) == 1
        assert filtered[0].signal_type == "oi_divergence"
