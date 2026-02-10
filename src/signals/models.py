"""Signal data models — the shared contract for all Phase 2 signal processors."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class MarketRegime(str, Enum):
    """Microstructure regime classifications."""

    DEAD = "dead"  # Wide spread, no activity
    QUIET = "quiet"  # Some depth, low message rate
    ACTIVE = "active"  # Tightening spread, building depth
    INFORMED = "informed"  # One-sided sweep, depth evaporating
    PRE_SETTLEMENT = "pre_settle"  # Converging toward 0 or 100
    UNKNOWN = "unknown"


class SignalDirection(str, Enum):
    BUY_YES = "buy_yes"
    BUY_NO = "buy_no"
    NEUTRAL = "neutral"


class SignalUrgency(str, Enum):
    IMMEDIATE = "immediate"  # Act now, edge is fleeting
    WATCH = "watch"  # Developing, monitor for confirmation
    BACKGROUND = "background"  # Informational, factor into models


class Signal(BaseModel):
    """Individual signal emitted by a signal processor."""

    signal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    signal_type: str
    market_ticker: str
    event_ticker: str | None = None
    series_ticker: str | None = None
    direction: SignalDirection
    strength: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    urgency: SignalUrgency
    metadata: dict = Field(default_factory=dict)
    ts: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    ttl_seconds: int = 300

    def is_expired(self) -> bool:
        now = datetime.now(tz=timezone.utc)
        ts_aware = self.ts if self.ts.tzinfo else self.ts.replace(tzinfo=timezone.utc)
        return (now - ts_aware).total_seconds() > self.ttl_seconds

    def to_redis_payload(self) -> str:
        return self.model_dump_json()


class CompositeSignal(BaseModel):
    """Output of the aggregator — one per market when actionable."""

    market_ticker: str
    event_ticker: str | None = None
    series_ticker: str | None = None
    direction: SignalDirection
    composite_score: float = Field(ge=-1.0, le=1.0)
    active_signals: list[Signal]
    regime: MarketRegime
    suggested_size: float | None = None  # Kelly-derived, Phase 3
    ts: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def to_redis_payload(self) -> str:
        return self.model_dump_json()
