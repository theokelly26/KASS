"""Pydantic model for Kalshi market lifecycle events from 'market_lifecycle_v2' channel."""

from __future__ import annotations

from datetime import datetime, timezone

import orjson
from pydantic import BaseModel, Field


class MarketLifecycleEvent(BaseModel):
    """A market lifecycle state change from the 'market_lifecycle_v2' channel."""

    market_ticker: str
    market_id: str
    status: str  # "open", "closed", "settled", etc.
    ts: int = Field(description="Unix timestamp in seconds")

    model_config = {"frozen": True}

    @property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.ts, tz=timezone.utc)

    def to_db_row(self) -> dict:
        """Return a dict matching the lifecycle_events table columns."""
        return {
            "ts": self.timestamp,
            "market_ticker": self.market_ticker,
            "market_id": self.market_id,
            "status": self.status,
        }

    def to_redis_payload(self) -> str:
        return orjson.dumps(self.model_dump()).decode()
