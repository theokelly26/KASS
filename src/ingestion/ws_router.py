"""Routes incoming WebSocket messages to appropriate handlers by type."""

from __future__ import annotations

# Message type → handler method name mapping
MESSAGE_HANDLERS: dict[str, str] = {
    "trade": "_handle_trade",
    "ticker": "_handle_ticker_v2",  # legacy, route same as ticker_v2
    "ticker_v2": "_handle_ticker_v2",
    "orderbook_snapshot": "_handle_orderbook_snapshot",
    "orderbook_delta": "_handle_orderbook_delta",
    "market_lifecycle_v2": "_handle_lifecycle",
    "event_lifecycle": "_handle_event_lifecycle",
    "subscribed": "_handle_subscribed",
    "unsubscribed": "_handle_unsubscribed",
    "error": "_handle_error",
    "ok": "_handle_ok",
}
