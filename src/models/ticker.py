"""Pydantic model for Kalshi ticker_v2 websocket channel messages."""

from __future__ import annotations

from datetime import datetime, timezone

import orjson
from pydantic import BaseModel, Field


class KalshiTickerV2(BaseModel):
    """A ticker update from the Kalshi 'ticker_v2' websocket channel.

    Fields are optional because ticker_v2 may send a subset of fields
    on each update (only changed values).
    """

    market_ticker: str
    market_id: str
    price: int | None = Field(default=None, ge=0, le=99)
    price_dollars: str | None = None
    volume_delta: int | None = None
    volume_delta_fp: str | None = None
    open_interest_delta: int | None = None
    open_interest_delta_fp: str | None = None
    dollar_volume_delta: int | None = None
    dollar_open_interest_delta: int | None = None
    ts: int = Field(description="Unix timestamp in seconds")

    model_config = {"frozen": True}

    @property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.ts, tz=timezone.utc)

    def to_db_row(self) -> dict:
        """Return a dict matching the ticker_updates table columns."""
        return {
            "ts": self.timestamp,
            "market_ticker": self.market_ticker,
            "price": self.price,
            "volume_delta": float(self.volume_delta_fp) if self.volume_delta_fp else None,
            "open_interest_delta": (
                float(self.open_interest_delta_fp) if self.open_interest_delta_fp else None
            ),
            "dollar_volume_delta": self.dollar_volume_delta,
            "dollar_open_interest_delta": self.dollar_open_interest_delta,
        }

    def to_redis_payload(self) -> str:
        return orjson.dumps(self.model_dump()).decode()
