"""Unit tests for market discovery components."""

from __future__ import annotations

import pytest

from src.models import KalshiMarket


class TestMarketParsing:
    """Test that REST API market responses parse correctly."""

    def test_full_market(self, sample_market_msg: dict) -> None:
        market = KalshiMarket.model_validate(sample_market_msg)
        assert market.ticker == "INXD-25FEB07-B5550"
        assert market.event_ticker == "INXD-25FEB07"
        assert market.series_ticker == "INXD"
        assert market.status == "open"
        assert market.volume == 5000

    def test_minimal_market(self) -> None:
        """Market with only required fields."""
        market = KalshiMarket.model_validate(
            {
                "ticker": "TEST-MARKET",
                "event_ticker": "TEST-EVENT",
                "series_ticker": "TEST",
                "market_type": "binary",
                "title": "Test Market Title",
                "status": "open",
            }
        )
        assert market.ticker == "TEST-MARKET"
        assert market.yes_bid is None
        assert market.volume is None
        assert market.close_time is None

    def test_market_to_db_row_keys(self, sample_market_msg: dict) -> None:
        market = KalshiMarket.model_validate(sample_market_msg)
        row = market.to_db_row()

        expected_keys = {
            "ticker",
            "event_ticker",
            "series_ticker",
            "title",
            "subtitle",
            "status",
            "market_type",
            "close_time",
            "result",
        }
        assert set(row.keys()) == expected_keys

    def test_market_redis_payload_is_json(self, sample_market_msg: dict) -> None:
        market = KalshiMarket.model_validate(sample_market_msg)
        payload = market.to_redis_payload()
        assert isinstance(payload, str)
        assert "INXD-25FEB07-B5550" in payload

    def test_multiple_markets_batch(self) -> None:
        """Simulate parsing a batch of markets from API."""
        markets_raw = [
            {
                "ticker": f"MKT-{i}",
                "event_ticker": f"EVT-{i}",
                "series_ticker": "SERIES",
                "market_type": "binary",
                "title": f"Market {i}",
                "status": "open",
            }
            for i in range(100)
        ]

        markets = [KalshiMarket.model_validate(m) for m in markets_raw]
        assert len(markets) == 100
        assert all(m.status == "open" for m in markets)
