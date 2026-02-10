"""Unit tests for Pydantic data models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models import (
    KalshiTrade,
    KalshiTickerV2,
    OrderbookSnapshot,
    OrderbookDelta,
    KalshiMarket,
    MarketLifecycleEvent,
)


class TestKalshiTrade:
    def test_valid_trade(self, sample_trade_msg: dict) -> None:
        trade = KalshiTrade.model_validate(sample_trade_msg)
        assert trade.trade_id == "abc123"
        assert trade.market_ticker == "INXD-25FEB07-B5550"
        assert trade.yes_price == 36
        assert trade.no_price == 64
        assert trade.taker_side == "yes"

    def test_to_db_row(self, sample_trade_msg: dict) -> None:
        trade = KalshiTrade.model_validate(sample_trade_msg)
        row = trade.to_db_row()
        assert row["trade_id"] == "abc123"
        assert row["market_ticker"] == "INXD-25FEB07-B5550"
        assert row["yes_price"] == 36
        assert row["count"] == 10.0
        assert row["ts"] is not None

    def test_to_redis_payload(self, sample_trade_msg: dict) -> None:
        trade = KalshiTrade.model_validate(sample_trade_msg)
        payload = trade.to_redis_payload()
        assert isinstance(payload, str)
        assert "abc123" in payload

    def test_invalid_price(self, sample_trade_msg: dict) -> None:
        sample_trade_msg["yes_price"] = 150
        with pytest.raises(ValidationError):
            KalshiTrade.model_validate(sample_trade_msg)

    def test_invalid_taker_side(self, sample_trade_msg: dict) -> None:
        sample_trade_msg["taker_side"] = "invalid"
        with pytest.raises(ValidationError):
            KalshiTrade.model_validate(sample_trade_msg)


class TestKalshiTickerV2:
    def test_full_ticker(self, sample_ticker_msg: dict) -> None:
        ticker = KalshiTickerV2.model_validate(sample_ticker_msg)
        assert ticker.market_ticker == "INXD-25FEB07-B5550"
        assert ticker.price == 36
        assert ticker.volume_delta == 10

    def test_partial_ticker(self, sample_ticker_partial_msg: dict) -> None:
        ticker = KalshiTickerV2.model_validate(sample_ticker_partial_msg)
        assert ticker.price == 37
        assert ticker.volume_delta is None
        assert ticker.open_interest_delta is None

    def test_to_db_row(self, sample_ticker_msg: dict) -> None:
        ticker = KalshiTickerV2.model_validate(sample_ticker_msg)
        row = ticker.to_db_row()
        assert row["market_ticker"] == "INXD-25FEB07-B5550"
        assert row["price"] == 36
        assert row["volume_delta"] == 10.0

    def test_partial_to_db_row(self, sample_ticker_partial_msg: dict) -> None:
        ticker = KalshiTickerV2.model_validate(sample_ticker_partial_msg)
        row = ticker.to_db_row()
        assert row["volume_delta"] is None
        assert row["open_interest_delta"] is None


class TestOrderbookSnapshot:
    def test_valid_snapshot(self, sample_orderbook_snapshot_msg: dict) -> None:
        snap = OrderbookSnapshot.model_validate(sample_orderbook_snapshot_msg)
        assert snap.market_ticker == "INXD-25FEB07-B5550"
        assert len(snap.yes) == 3
        assert len(snap.no) == 3

    def test_depth(self, sample_orderbook_snapshot_msg: dict) -> None:
        snap = OrderbookSnapshot.model_validate(sample_orderbook_snapshot_msg)
        assert snap.yes_depth_5 == 450  # 100 + 200 + 150
        assert snap.no_depth_5 == 290  # 80 + 120 + 90

    def test_to_db_row(self, sample_orderbook_snapshot_msg: dict) -> None:
        snap = OrderbookSnapshot.model_validate(sample_orderbook_snapshot_msg)
        row = snap.to_db_row()
        assert row["market_ticker"] == "INXD-25FEB07-B5550"
        assert row["yes_depth_5"] == 450
        assert row["ts"] is not None


class TestOrderbookDelta:
    def test_valid_delta(self, sample_orderbook_delta_msg: dict) -> None:
        delta = OrderbookDelta.model_validate(sample_orderbook_delta_msg)
        assert delta.market_ticker == "INXD-25FEB07-B5550"
        assert delta.price == 36
        assert delta.delta == -20
        assert delta.side == "yes"
        assert delta.is_own_order is False

    def test_own_order(self, sample_orderbook_delta_msg: dict) -> None:
        sample_orderbook_delta_msg["client_order_id"] = "my-order-123"
        delta = OrderbookDelta.model_validate(sample_orderbook_delta_msg)
        assert delta.is_own_order is True

    def test_to_db_row(self, sample_orderbook_delta_msg: dict) -> None:
        delta = OrderbookDelta.model_validate(sample_orderbook_delta_msg)
        row = delta.to_db_row()
        assert row["delta"] == -20.0
        assert row["is_own_order"] is False


class TestKalshiMarket:
    def test_valid_market(self, sample_market_msg: dict) -> None:
        market = KalshiMarket.model_validate(sample_market_msg)
        assert market.ticker == "INXD-25FEB07-B5550"
        assert market.event_ticker == "INXD-25FEB07"
        assert market.series_ticker == "INXD"
        assert market.status == "open"

    def test_to_db_row(self, sample_market_msg: dict) -> None:
        market = KalshiMarket.model_validate(sample_market_msg)
        row = market.to_db_row()
        assert row["ticker"] == "INXD-25FEB07-B5550"
        assert row["event_ticker"] == "INXD-25FEB07"

    def test_nullable_fields(self) -> None:
        market = KalshiMarket.model_validate(
            {
                "ticker": "TEST",
                "event_ticker": "TEST-EVENT",
                "series_ticker": "TEST-SERIES",
                "market_type": "binary",
                "title": "Test Market",
                "status": "open",
            }
        )
        assert market.subtitle is None
        assert market.yes_bid is None
        assert market.volume is None


class TestMarketLifecycleEvent:
    def test_valid_lifecycle(self, sample_lifecycle_msg: dict) -> None:
        event = MarketLifecycleEvent.model_validate(sample_lifecycle_msg)
        assert event.market_ticker == "INXD-25FEB07-B5550"
        assert event.status == "closed"

    def test_to_db_row(self, sample_lifecycle_msg: dict) -> None:
        event = MarketLifecycleEvent.model_validate(sample_lifecycle_msg)
        row = event.to_db_row()
        assert row["market_ticker"] == "INXD-25FEB07-B5550"
        assert row["status"] == "closed"
        assert row["ts"] is not None
