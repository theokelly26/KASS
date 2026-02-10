"""Integration test for the Phase 2 signal pipeline.

Requires running Redis. Skipped by default.
Run with: pytest tests/integration/test_signal_pipeline.py -v
"""

from __future__ import annotations

import pytest

from src.signals.models import (
    CompositeSignal,
    MarketRegime,
    Signal,
    SignalDirection,
    SignalUrgency,
)


@pytest.mark.skip(reason="Requires running Redis infrastructure")
class TestSignalPipeline:
    """End-to-end signal pipeline integration test."""

    async def test_publish_and_read_signal(self) -> None:
        """Publish a signal to a stream, verify it's readable."""
        from src.cache.redis_client import get_redis
        from src.config import get_config
        from src.signals.streams import SignalPublisher, STREAM_FLOW_TOXICITY

        config = get_config()
        redis = await get_redis(config.redis)
        publisher = SignalPublisher(redis)

        signal = Signal(
            signal_type="flow_toxicity",
            market_ticker="TEST-INTEGRATION",
            direction=SignalDirection.BUY_YES,
            strength=0.8,
            confidence=0.7,
            urgency=SignalUrgency.WATCH,
        )

        msg_id = await publisher.publish(STREAM_FLOW_TOXICITY, signal)
        assert msg_id

        # Read back
        recent = await publisher.get_recent_signals(STREAM_FLOW_TOXICITY, count=5)
        assert any(s.market_ticker == "TEST-INTEGRATION" for s in recent)

    async def test_get_active_signals_for_market(self) -> None:
        """Verify we can query active signals for a specific market."""
        from src.cache.redis_client import get_redis
        from src.config import get_config
        from src.signals.streams import SignalPublisher, STREAM_OI_DIVERGENCE

        config = get_config()
        redis = await get_redis(config.redis)
        publisher = SignalPublisher(redis)

        signal = Signal(
            signal_type="oi_divergence",
            market_ticker="TEST-ACTIVE-QUERY",
            direction=SignalDirection.BUY_NO,
            strength=0.6,
            confidence=0.5,
            urgency=SignalUrgency.BACKGROUND,
        )
        await publisher.publish(STREAM_OI_DIVERGENCE, signal)

        active = await publisher.get_active_signals_for_market("TEST-ACTIVE-QUERY")
        assert len(active) >= 1

    async def test_composite_serialization_roundtrip(self) -> None:
        """Verify composite signals serialize and deserialize correctly."""
        signal = Signal(
            signal_type="flow_toxicity",
            market_ticker="TEST",
            direction=SignalDirection.BUY_YES,
            strength=0.8,
            confidence=0.7,
            urgency=SignalUrgency.WATCH,
        )
        composite = CompositeSignal(
            market_ticker="TEST",
            direction=SignalDirection.BUY_YES,
            composite_score=0.65,
            active_signals=[signal],
            regime=MarketRegime.ACTIVE,
        )
        payload = composite.to_redis_payload()
        restored = CompositeSignal.model_validate_json(payload)
        assert restored.composite_score == 0.65
        assert restored.regime == MarketRegime.ACTIVE
        assert len(restored.active_signals) == 1
