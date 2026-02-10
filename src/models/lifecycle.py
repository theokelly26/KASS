"""Pydantic models for Kalshi lifecycle events from the 'market_lifecycle_v2' channel."""

from __future__ import annotations

from datetime import datetime, timezone

import orjson
from pydantic import BaseModel, Field


class MarketLifecycleEvent(BaseModel):
    """A market lifecycle state change from the 'market_lifecycle_v2' channel.

    Real messages vary by event_type:
      - close_date_updated: {market_ticker, close_ts, event_type}
      - determined: {market_ticker, determination_ts, result, event_type}
      - open/closed/settled: varies
    """

    market_ticker: str
    event_type: str = ""
    # Optional fields that appear depending on event_type
    market_id: str = ""
    status: str = ""
    result: str = ""
    close_ts: int | None = None
    determination_ts: int | None = None
    ts: int | None = None

    model_config = {"frozen": True, "extra": "allow"}

    @property
    def timestamp(self) -> datetime:
        """Best-effort timestamp from whichever field is present."""
        if self.ts is not None:
            return datetime.fromtimestamp(self.ts, tz=timezone.utc)
        if self.determination_ts is not None:
            return datetime.fromtimestamp(self.determination_ts, tz=timezone.utc)
        if self.close_ts is not None:
            return datetime.fromtimestamp(self.close_ts, tz=timezone.utc)
        return datetime.now(tz=timezone.utc)

    def to_db_row(self) -> dict:
        """Return a dict matching the lifecycle_events table columns."""
        return {
            "ts": self.timestamp,
            "market_ticker": self.market_ticker,
            "market_id": self.market_id or None,
            "status": self.event_type or self.status or "unknown",
        }

    def to_redis_payload(self) -> str:
        return orjson.dumps(self.model_dump()).decode()


class EventLifecycleEvent(BaseModel):
    """An event-level lifecycle message (new event creation, etc.)."""

    event_ticker: str
    title: str = ""
    subtitle: str = ""
    collateral_return_type: str = ""
    series_ticker: str = ""

    model_config = {"frozen": True}

    def to_redis_payload(self) -> str:
        return orjson.dumps(self.model_dump()).decode()
