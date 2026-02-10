"""Unit tests for persistence layer (writers, gap detection)."""

from __future__ import annotations

import pytest

from src.models import KalshiTrade, KalshiTickerV2, OrderbookDelta, MarketLifecycleEvent


class TestTradeWriterDataPrep:
    """Test that trade data is correctly prepared for DB insertion."""

    def test_trade_to_db_row_types(self, sample_trade_msg: dict) -> None:
        trade = KalshiTrade.model_validate(sample_trade_msg)
        row = trade.to_db_row()

        assert isinstance(row["trade_id"], str)
        assert isinstance(row["market_ticker"], str)
        assert isinstance(row["yes_price"], int)
        assert isinstance(row["no_price"], int)
        assert isinstance(row["count"], float)
        assert row["taker_side"] in ("yes", "no")

    def test_trade_timestamp_conversion(self, sample_trade_msg: dict) -> None:
        trade = KalshiTrade.model_validate(sample_trade_msg)
        row = trade.to_db_row()
        assert row["ts"].tzinfo is not None  # Must be timezone-aware


class TestTickerWriterDataPrep:
    def test_full_ticker_to_db_row(self, sample_ticker_msg: dict) -> None:
        ticker = KalshiTickerV2.model_validate(sample_ticker_msg)
        row = ticker.to_db_row()

        assert row["market_ticker"] == "INXD-25FEB07-B5550"
        assert row["price"] == 36
        assert row["volume_delta"] == 10.0
        assert row["open_interest_delta"] == 5.0

    def test_partial_ticker_null_handling(self, sample_ticker_partial_msg: dict) -> None:
        ticker = KalshiTickerV2.model_validate(sample_ticker_partial_msg)
        row = ticker.to_db_row()

        assert row["price"] == 37
        assert row["volume_delta"] is None
        assert row["open_interest_delta"] is None
        assert row["dollar_volume_delta"] is None


class TestOrderbookDeltaDataPrep:
    def test_delta_to_db_row(self, sample_orderbook_delta_msg: dict) -> None:
        delta = OrderbookDelta.model_validate(sample_orderbook_delta_msg)
        row = delta.to_db_row()

        assert row["price"] == 36
        assert row["delta"] == -20.0
        assert row["side"] == "yes"
        assert row["is_own_order"] is False


class TestLifecycleDataPrep:
    def test_lifecycle_to_db_row(self, sample_lifecycle_msg: dict) -> None:
        event = MarketLifecycleEvent.model_validate(sample_lifecycle_msg)
        row = event.to_db_row()

        assert row["market_ticker"] == "INXD-25FEB07-B5550"
        assert row["status"] == "closed"
        assert row["market_id"] == "market-123"
