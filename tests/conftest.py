"""Shared test fixtures for KASS test suite."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_trade_msg() -> dict:
    """Sample trade message as received from Kalshi WebSocket."""
    return {
        "trade_id": "abc123",
        "market_ticker": "INXD-25FEB07-B5550",
        "yes_price": 36,
        "yes_price_dollars": "0.360",
        "no_price": 64,
        "no_price_dollars": "0.640",
        "count": 10,
        "count_fp": "10.00",
        "taker_side": "yes",
        "ts": 1707350400,
    }


@pytest.fixture
def sample_ticker_msg() -> dict:
    """Sample ticker_v2 message."""
    return {
        "market_ticker": "INXD-25FEB07-B5550",
        "market_id": "market-123",
        "price": 36,
        "price_dollars": "0.360",
        "volume_delta": 10,
        "volume_delta_fp": "10.00",
        "open_interest_delta": 5,
        "open_interest_delta_fp": "5.00",
        "dollar_volume_delta": 360,
        "dollar_open_interest_delta": 180,
        "ts": 1707350400,
    }


@pytest.fixture
def sample_ticker_partial_msg() -> dict:
    """Sample ticker_v2 with only a subset of fields."""
    return {
        "market_ticker": "INXD-25FEB07-B5550",
        "market_id": "market-123",
        "price": 37,
        "ts": 1707350460,
    }


@pytest.fixture
def sample_orderbook_snapshot_msg() -> dict:
    """Sample orderbook snapshot."""
    return {
        "market_ticker": "INXD-25FEB07-B5550",
        "market_id": "market-123",
        "yes": [[36, 100], [35, 200], [34, 150]],
        "yes_dollars": [["0.36", 100], ["0.35", 200], ["0.34", 150]],
        "no": [[64, 80], [65, 120], [66, 90]],
        "no_dollars": [["0.64", 80], ["0.65", 120], ["0.66", 90]],
    }


@pytest.fixture
def sample_orderbook_delta_msg() -> dict:
    """Sample orderbook delta."""
    return {
        "market_ticker": "INXD-25FEB07-B5550",
        "market_id": "market-123",
        "price": 36,
        "price_dollars": "0.360",
        "delta": -20,
        "delta_fp": "-20.00",
        "side": "yes",
        "ts": "2024-02-08T12:00:00Z",
    }


@pytest.fixture
def sample_market_msg() -> dict:
    """Sample market metadata from REST API."""
    return {
        "ticker": "INXD-25FEB07-B5550",
        "event_ticker": "INXD-25FEB07",
        "series_ticker": "INXD",
        "market_type": "binary",
        "title": "S&P 500 above 5550 on Feb 7?",
        "subtitle": "Resolves to Yes if...",
        "status": "open",
        "yes_bid": 35,
        "yes_ask": 37,
        "last_price": 36,
        "volume": 5000,
        "open_interest": 2500,
        "close_time": "2025-02-07T21:00:00Z",
        "result": None,
    }


@pytest.fixture
def sample_lifecycle_msg() -> dict:
    """Sample lifecycle event."""
    return {
        "market_ticker": "INXD-25FEB07-B5550",
        "market_id": "market-123",
        "status": "closed",
        "ts": 1707350400,
    }
