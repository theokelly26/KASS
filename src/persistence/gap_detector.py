"""Detects gaps in ingested data by analyzing time intervals between records."""

from __future__ import annotations

from datetime import datetime, timedelta

import structlog

from src.config import PostgresConfig
from src.persistence.db import get_connection

logger = structlog.get_logger(__name__)


class GapDetector:
    """
    Detects gaps in the data by comparing expected vs actual records.
    """

    def __init__(self, pg_config: PostgresConfig) -> None:
        self._pg_config = pg_config

    async def check_trade_continuity(
        self,
        market_ticker: str,
        start: datetime,
        end: datetime,
        max_gap_seconds: int = 300,
    ) -> list[tuple[datetime, datetime]]:
        """
        Query trades table for a market in a time range.
        Detect gaps > max_gap_seconds between consecutive trades.
        Returns list of (gap_start, gap_end) tuples.
        """
        gaps: list[tuple[datetime, datetime]] = []

        async with get_connection(self._pg_config) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT ts,
                           LEAD(ts) OVER (ORDER BY ts) as next_ts
                    FROM trades
                    WHERE market_ticker = %s AND ts BETWEEN %s AND %s
                    ORDER BY ts
                    """,
                    (market_ticker, start, end),
                )
                rows = await cur.fetchall()

        for row in rows:
            ts, next_ts = row
            if next_ts is None:
                continue
            delta = (next_ts - ts).total_seconds()
            if delta > max_gap_seconds:
                gaps.append((ts, next_ts))

        if gaps:
            logger.warning(
                "trade_gaps_detected",
                market_ticker=market_ticker,
                gap_count=len(gaps),
                total_gap_seconds=sum(
                    (e - s).total_seconds() for s, e in gaps
                ),
            )

        return gaps

    async def check_ticker_continuity(
        self,
        market_ticker: str,
        start: datetime,
        end: datetime,
        max_gap_seconds: int = 600,
    ) -> list[tuple[datetime, datetime]]:
        """Similar gap detection for ticker updates."""
        gaps: list[tuple[datetime, datetime]] = []

        async with get_connection(self._pg_config) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT ts,
                           LEAD(ts) OVER (ORDER BY ts) as next_ts
                    FROM ticker_updates
                    WHERE market_ticker = %s AND ts BETWEEN %s AND %s
                    ORDER BY ts
                    """,
                    (market_ticker, start, end),
                )
                rows = await cur.fetchall()

        for row in rows:
            ts, next_ts = row
            if next_ts is None:
                continue
            delta = (next_ts - ts).total_seconds()
            if delta > max_gap_seconds:
                gaps.append((ts, next_ts))

        if gaps:
            logger.warning(
                "ticker_gaps_detected",
                market_ticker=market_ticker,
                gap_count=len(gaps),
            )

        return gaps

    async def check_all_active_markets(
        self,
        lookback_hours: int = 24,
    ) -> dict[str, list[tuple[datetime, datetime]]]:
        """Run gap detection on all active markets."""
        now = datetime.utcnow()
        start = now - timedelta(hours=lookback_hours)
        results: dict[str, list[tuple[datetime, datetime]]] = {}

        async with get_connection(self._pg_config) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT ticker FROM markets WHERE status = 'open'"
                )
                tickers = [row[0] for row in await cur.fetchall()]

        for ticker in tickers:
            gaps = await self.check_trade_continuity(ticker, start, now)
            if gaps:
                results[ticker] = gaps

        logger.info(
            "gap_check_complete",
            markets_checked=len(tickers),
            markets_with_gaps=len(results),
        )
        return results
