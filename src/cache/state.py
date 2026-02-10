"""Orderbook and ticker state management in Redis."""

from __future__ import annotations

import orjson
import redis.asyncio as aioredis
import structlog

from src.models import OrderbookSnapshot, OrderbookDelta

logger = structlog.get_logger(__name__)

# Key patterns
KEY_ORDERBOOK = "state:orderbook:{ticker}"
KEY_TICKER = "state:ticker:{ticker}"
KEY_MARKETS = "meta:markets"
KEY_SERIES = "meta:series:{ticker}"
KEY_HEALTH = "health:{component}"


class OrderbookStateManager:
    """Maintains current orderbook state in Redis from snapshot + deltas."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def apply_snapshot(self, snapshot: OrderbookSnapshot) -> None:
        """Replace the entire orderbook state for a market with a fresh snapshot."""
        key = KEY_ORDERBOOK.format(ticker=snapshot.market_ticker)
        book = {
            "market_ticker": snapshot.market_ticker,
            "yes": {str(level[0]): level[1] for level in snapshot.yes},
            "no": {str(level[0]): level[1] for level in snapshot.no},
        }
        await self._redis.set(key, orjson.dumps(book).decode())
        logger.debug("orderbook_snapshot_applied", ticker=snapshot.market_ticker)

    async def apply_delta(self, delta: OrderbookDelta) -> None:
        """Apply an incremental change to the orderbook state."""
        key = KEY_ORDERBOOK.format(ticker=delta.market_ticker)
        raw = await self._redis.get(key)
        if raw is None:
            logger.warning("orderbook_delta_no_snapshot", ticker=delta.market_ticker)
            return

        book = orjson.loads(raw)
        side = book[delta.side]
        price_key = str(delta.price)

        current_qty = side.get(price_key, 0)
        new_qty = current_qty + delta.delta

        if new_qty <= 0:
            side.pop(price_key, None)
        else:
            side[price_key] = new_qty

        await self._redis.set(key, orjson.dumps(book).decode())

    async def get_current_book(self, ticker: str) -> dict | None:
        """Get the current reconstructed orderbook for a market."""
        key = KEY_ORDERBOOK.format(ticker=ticker)
        raw = await self._redis.get(key)
        if raw is None:
            return None
        return orjson.loads(raw)

    async def get_spread(self, ticker: str) -> int | None:
        """Get the current bid-ask spread for a market."""
        book = await self.get_current_book(ticker)
        if book is None:
            return None

        yes_levels = book.get("yes", {})
        no_levels = book.get("no", {})

        if not yes_levels or not no_levels:
            return None

        # Best yes bid = highest price with quantity on yes side
        best_yes_bid = max(int(p) for p in yes_levels.keys()) if yes_levels else None
        # Best no bid = highest price on no side
        best_no_bid = max(int(p) for p in no_levels.keys()) if no_levels else None

        if best_yes_bid is None or best_no_bid is None:
            return None

        # In a binary market: spread = 100 - best_yes_bid - best_no_bid
        return 100 - best_yes_bid - best_no_bid

    async def get_midpoint(self, ticker: str) -> float | None:
        """Get the midpoint price for a market."""
        book = await self.get_current_book(ticker)
        if book is None:
            return None

        yes_levels = book.get("yes", {})
        no_levels = book.get("no", {})

        if not yes_levels or not no_levels:
            return None

        best_yes_bid = max(int(p) for p in yes_levels.keys()) if yes_levels else None
        best_no_bid = max(int(p) for p in no_levels.keys()) if no_levels else None

        if best_yes_bid is None or best_no_bid is None:
            return None

        best_yes_ask = 100 - best_no_bid
        return (best_yes_bid + best_yes_ask) / 2.0
