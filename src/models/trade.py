"""Pydantic model for Kalshi trade messages from the 'trade' websocket channel."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

import orjson
from pydantic import BaseModel, Field


class KalshiTrade(BaseModel):
    """A single trade from the Kalshi 'trade' websocket channel."""

    trade_id: str
    market_ticker: str
    yes_price: int = Field(ge=0, le=99, description="Price in cents (0-99)")
    yes_price_dollars: str = Field(description="e.g. '0.360'")
    no_price: int = Field(ge=0, le=99)
    no_price_dollars: str
    count: int = Field(ge=1, description="Contract count")
    count_fp: str = Field(description="Fixed-point e.g. '136.00'")
    taker_side: Literal["yes", "no"]
    ts: int = Field(description="Unix timestamp in seconds")

    model_config = {"frozen": True}

    @property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.ts, tz=timezone.utc)

    def to_db_row(self) -> dict:
        """Return a dict matching the trades table columns."""
        return {
            "ts": self.timestamp,
            "trade_id": self.trade_id,
            "market_ticker": self.market_ticker,
            "yes_price": self.yes_price,
            "no_price": self.no_price,
            "count": float(self.count_fp),
            "taker_side": self.taker_side,
        }

    def to_redis_payload(self) -> str:
        """Return a JSON string for Redis stream publishing."""
        return orjson.dumps(self.model_dump()).decode()
