"""Maps the hierarchical relationship between series, events, and markets.

Critical for cross-market signal propagation in Phase 2.
"""

from __future__ import annotations

import orjson
import redis.asyncio as aioredis
import structlog

from src.cache.state import KEY_SERIES
from src.persistence.db import get_connection
from src.config import PostgresConfig

logger = structlog.get_logger(__name__)


class SeriesMapper:
    """Maps the hierarchical relationship between series -> events -> markets."""

    def __init__(self, redis: aioredis.Redis, pg_config: PostgresConfig) -> None:
        self._redis = redis
        self._pg_config = pg_config

    async def get_related_markets(self, ticker: str) -> list[str]:
        """Given a market ticker, return all markets in the same event."""
        async with get_connection(self._pg_config) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT m2.ticker FROM markets m1
                    JOIN markets m2 ON m1.event_ticker = m2.event_ticker
                    WHERE m1.ticker = %s AND m2.ticker != %s
                    """,
                    (ticker, ticker),
                )
                return [row[0] for row in await cur.fetchall()]

    async def get_event_markets(self, event_ticker: str) -> list[str]:
        """Get all markets for an event."""
        async with get_connection(self._pg_config) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT ticker FROM markets WHERE event_ticker = %s",
                    (event_ticker,),
                )
                return [row[0] for row in await cur.fetchall()]

    async def get_series_events(self, series_ticker: str) -> list[str]:
        """Get all events in a series."""
        async with get_connection(self._pg_config) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT ticker FROM events WHERE series_ticker = %s",
                    (series_ticker,),
                )
                return [row[0] for row in await cur.fetchall()]

    async def build_market_graph(self) -> dict:
        """
        Build the full series -> event -> market relationship graph.
        Store in Redis for fast lookups.

        Returns:
            {
                "series_ticker": {
                    "events": {
                        "event_ticker": {
                            "markets": ["market_ticker_1", ...]
                        }
                    }
                }
            }
        """
        graph: dict = {}

        async with get_connection(self._pg_config) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT m.series_ticker, m.event_ticker, m.ticker
                    FROM markets m
                    WHERE m.status = 'open'
                    ORDER BY m.series_ticker, m.event_ticker, m.ticker
                    """
                )
                rows = await cur.fetchall()

        for series_ticker, event_ticker, market_ticker in rows:
            if series_ticker not in graph:
                graph[series_ticker] = {"events": {}}
            events = graph[series_ticker]["events"]
            if event_ticker not in events:
                events[event_ticker] = {"markets": []}
            events[event_ticker]["markets"].append(market_ticker)

        # Store each series in Redis
        for series_ticker, data in graph.items():
            key = KEY_SERIES.format(ticker=series_ticker)
            await self._redis.set(key, orjson.dumps(data).decode(), ex=300)

        logger.info(
            "market_graph_built",
            series_count=len(graph),
            event_count=sum(
                len(s["events"]) for s in graph.values()
            ),
            market_count=sum(
                len(m["markets"])
                for s in graph.values()
                for m in s["events"].values()
            ),
        )

        return graph
