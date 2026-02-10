"""Pydantic model for Kalshi market metadata from REST API."""

from __future__ import annotations

from datetime import datetime

import orjson
from pydantic import BaseModel


class KalshiMarket(BaseModel):
    """Market metadata fetched from the Kalshi REST API."""

    ticker: str
    event_ticker: str
    series_ticker: str
    market_type: str
    title: str
    subtitle: str | None = None
    status: str  # "open", "closed", "settled", etc.
    yes_bid: int | None = None
    yes_ask: int | None = None
    last_price: int | None = None
    volume: int | None = None
    open_interest: int | None = None
    close_time: datetime | None = None
    result: str | None = None

    model_config = {"frozen": True}

    def to_db_row(self) -> dict:
        """Return a dict matching the markets table columns."""
        return {
            "ticker": self.ticker,
            "event_ticker": self.event_ticker,
            "series_ticker": self.series_ticker,
            "title": self.title,
            "subtitle": self.subtitle,
            "status": self.status,
            "market_type": self.market_type,
            "close_time": self.close_time,
            "result": self.result,
        }

    def to_redis_payload(self) -> str:
        return orjson.dumps(self.model_dump(), default=str).decode()
