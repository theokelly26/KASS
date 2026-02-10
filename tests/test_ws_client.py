"""Unit tests for WebSocket client message handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ingestion.ws_client import KalshiWSManager


@pytest.fixture
def mock_manager() -> KalshiWSManager:
    """Create a KalshiWSManager with mocked dependencies."""
    auth = MagicMock()
    publisher = AsyncMock()
    publisher.publish_trade = AsyncMock(return_value="msg-1")
    publisher.publish_ticker = AsyncMock(return_value="msg-2")
    publisher.publish_orderbook_delta = AsyncMock(return_value="msg-3")
    publisher.publish_orderbook_snapshot = AsyncMock(return_value="msg-4")
    publisher.publish_lifecycle = AsyncMock(return_value="msg-5")
    publisher.get_counts = MagicMock(return_value={})

    state_mgr = AsyncMock()

    config = MagicMock()
    config.kalshi.ws_url = "wss://demo-api.kalshi.co/trade-api/ws/v2"
    config.tuning.ws_ping_interval = 30
    config.tuning.ws_pong_timeout = 10
    config.tuning.ws_reconnect_max_delay = 60

    return KalshiWSManager(auth, publisher, state_mgr, config)


class TestSubscriptionManagement:
    async def test_subscribe_adds_to_dict(self, mock_manager: KalshiWSManager) -> None:
        sid = await mock_manager.subscribe(["ticker_v2"])
        assert sid in mock_manager.subscriptions
        assert mock_manager.subscriptions[sid].channels == ["ticker_v2"]

    async def test_subscribe_with_tickers(self, mock_manager: KalshiWSManager) -> None:
        sid = await mock_manager.subscribe(
            ["orderbook_delta"], market_tickers=["INXD-25FEB07-B5550"]
        )
        sub = mock_manager.subscriptions[sid]
        assert sub.market_tickers == ["INXD-25FEB07-B5550"]

    async def test_unsubscribe_removes_from_dict(self, mock_manager: KalshiWSManager) -> None:
        sid = await mock_manager.subscribe(["trade"])
        await mock_manager.unsubscribe([sid])
        assert sid not in mock_manager.subscriptions


class TestSequenceGapDetection:
    async def test_no_gap(self, mock_manager: KalshiWSManager) -> None:
        mock_manager.sequence_numbers[1] = 5
        assert await mock_manager._detect_sequence_gap(1, 6) is False

    async def test_gap_detected(self, mock_manager: KalshiWSManager) -> None:
        mock_manager.sequence_numbers[1] = 5
        assert await mock_manager._detect_sequence_gap(1, 8) is True

    async def test_first_message_no_gap(self, mock_manager: KalshiWSManager) -> None:
        # No previous sequence number — first message
        assert await mock_manager._detect_sequence_gap(1, 1) is False


class TestMessageHandlers:
    async def test_handle_trade(self, mock_manager: KalshiWSManager) -> None:
        msg = {
            "type": "trade",
            "msg": {
                "trade_id": "abc123",
                "market_ticker": "TEST",
                "yes_price": 36,
                "yes_price_dollars": "0.360",
                "no_price": 64,
                "no_price_dollars": "0.640",
                "count": 10,
                "count_fp": "10.00",
                "taker_side": "yes",
                "ts": 1707350400,
            },
        }
        await mock_manager._handle_trade(msg)
        mock_manager._publisher.publish_trade.assert_called_once()

    async def test_handle_ticker_v2(self, mock_manager: KalshiWSManager) -> None:
        msg = {
            "type": "ticker_v2",
            "msg": {
                "market_ticker": "TEST",
                "market_id": "m-123",
                "price": 36,
                "ts": 1707350400,
            },
        }
        await mock_manager._handle_ticker_v2(msg)
        mock_manager._publisher.publish_ticker.assert_called_once()

    async def test_handle_lifecycle(self, mock_manager: KalshiWSManager) -> None:
        msg = {
            "type": "market_lifecycle_v2",
            "msg": {
                "market_ticker": "TEST",
                "market_id": "m-123",
                "status": "closed",
                "ts": 1707350400,
            },
        }
        await mock_manager._handle_lifecycle(msg)
        mock_manager._publisher.publish_lifecycle.assert_called_once()

    async def test_handle_invalid_trade_doesnt_crash(
        self, mock_manager: KalshiWSManager
    ) -> None:
        """Malformed messages should be logged and skipped, not crash."""
        msg = {"type": "trade", "msg": {"invalid": "data"}}
        await mock_manager._handle_trade(msg)
        mock_manager._publisher.publish_trade.assert_not_called()
