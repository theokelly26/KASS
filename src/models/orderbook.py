"""Pydantic models for Kalshi orderbook snapshots and deltas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

import orjson
from pydantic import BaseModel, Field


class OrderbookSnapshot(BaseModel):
    """Full orderbook snapshot from the 'orderbook_snapshot' websocket message.

    Kalshi may omit the 'no'/'no_dollars' or 'yes'/'yes_dollars' fields when
    one side of the book is empty, so all four level fields default to [].
    """

    market_ticker: str
    market_id: str
    yes: list[list[int]] = Field(default_factory=list, description="[[price, quantity], ...]")
    yes_dollars: list[list[str | int]] = Field(default_factory=list, description="[['0.50', 100], ...]")
    no: list[list[int]] = Field(default_factory=list)
    no_dollars: list[list[str | int]] = Field(default_factory=list)

    model_config = {"frozen": True}

    @property
    def spread(self) -> int | None:
        """Best ask - best bid (yes side). Returns None if book is empty."""
        if not self.yes or not self.no:
            return None
        best_yes_ask = min(level[0] for level in self.yes) if self.yes else None
        best_no_ask = min(level[0] for level in self.no) if self.no else None
        if best_yes_ask is None or best_no_ask is None:
            return None
        return best_yes_ask + best_no_ask - 100  # spread in binary market terms

    @property
    def yes_depth_5(self) -> int:
        """Total quantity in the top 5 yes levels."""
        sorted_levels = sorted(self.yes, key=lambda x: x[0], reverse=True)
        return sum(level[1] for level in sorted_levels[:5])

    @property
    def no_depth_5(self) -> int:
        """Total quantity in the top 5 no levels."""
        sorted_levels = sorted(self.no, key=lambda x: x[0], reverse=True)
        return sum(level[1] for level in sorted_levels[:5])

    def to_db_row(self) -> dict:
        """Return a dict matching the orderbook_snapshots table columns."""
        return {
            "ts": datetime.now(tz=timezone.utc),
            "market_ticker": self.market_ticker,
            "yes_levels": orjson.dumps(self.yes).decode(),
            "no_levels": orjson.dumps(self.no).decode(),
            "spread": self.spread,
            "yes_depth_5": self.yes_depth_5,
            "no_depth_5": self.no_depth_5,
        }

    def to_redis_payload(self) -> str:
        return orjson.dumps(self.model_dump()).decode()


class OrderbookDelta(BaseModel):
    """A single orderbook change from the 'orderbook_delta' websocket channel."""

    market_ticker: str
    market_id: str
    price: int = Field(ge=0, le=99)
    price_dollars: str
    delta: int = Field(description="Signed quantity change")
    delta_fp: str
    side: Literal["yes", "no"]
    ts: str = Field(description="ISO 8601 timestamp")
    client_order_id: str | None = None

    model_config = {"frozen": True}

    @property
    def timestamp(self) -> datetime:
        return datetime.fromisoformat(self.ts)

    @property
    def is_own_order(self) -> bool:
        return self.client_order_id is not None

    def to_db_row(self) -> dict:
        """Return a dict matching the orderbook_deltas table columns."""
        return {
            "ts": self.timestamp,
            "market_ticker": self.market_ticker,
            "price": self.price,
            "delta": float(self.delta_fp),
            "side": self.side,
            "is_own_order": self.is_own_order,
        }

    def to_redis_payload(self) -> str:
        return orjson.dumps(self.model_dump()).decode()
