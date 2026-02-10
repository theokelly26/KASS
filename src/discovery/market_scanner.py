"""Market discovery service — polls Kalshi REST API for active markets.

Discovers new markets, maintains metadata tables, and coordinates
with the subscription manager for dynamic WebSocket subscriptions.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import orjson
import structlog

from src.config import AppConfig, get_config
from src.cache.redis_client import get_redis
from src.cache.state import KEY_MARKETS
from src.ingestion.rest_client import KalshiRESTClient
from src.ingestion.ws_auth import KalshiWSAuth
from src.models import KalshiMarket
from src.persistence.db import get_connection

logger = structlog.get_logger(__name__)


class MarketScanner:
    """
    Periodically polls Kalshi REST API to discover all active markets
    and maintain the markets/events/series metadata tables.
    """

    def __init__(self, rest_client: KalshiRESTClient, config: AppConfig) -> None:
        self._client = rest_client
        self._config = config
        self._known_tickers: set[str] = set()

    async def scan_all_markets(self) -> list[KalshiMarket]:
        """
        Paginate through all open markets.
        Upsert into markets table.
        Returns list of newly discovered markets.
        """
        all_markets: list[KalshiMarket] = []
        cursor: str | None = None

        while True:
            data = await self._client.get_markets(status="open", cursor=cursor)
            markets_raw = data.get("markets", [])
            if not markets_raw:
                break

            for m in markets_raw:
                try:
                    market = KalshiMarket.model_validate(m)
                    all_markets.append(market)
                except Exception:
                    logger.exception("market_parse_error", raw=m)

            cursor = data.get("cursor")
            if not cursor:
                break

        # Determine new and closed markets
        current_tickers = {m.ticker for m in all_markets}
        new_tickers = current_tickers - self._known_tickers
        closed_tickers = self._known_tickers - current_tickers

        new_markets = [m for m in all_markets if m.ticker in new_tickers]

        # Upsert all markets to DB
        await self._upsert_markets(all_markets)

        # Update Redis cache
        redis = await get_redis(self._config.redis)
        market_map = {m.ticker: m.to_redis_payload() for m in all_markets}
        if market_map:
            await redis.delete(KEY_MARKETS)
            await redis.hset(KEY_MARKETS, mapping=market_map)
            await redis.expire(KEY_MARKETS, 300)  # 5 min TTL

        self._known_tickers = current_tickers

        logger.info(
            "market_scan_complete",
            new=len(new_tickers),
            closed=len(closed_tickers),
            total_active=len(current_tickers),
        )

        return new_markets

    async def scan_events(self) -> None:
        """Populate events table with event metadata."""
        cursor: str | None = None

        while True:
            data = await self._client.get_events(cursor=cursor)
            events = data.get("events", [])
            if not events:
                break

            await self._upsert_events(events)

            cursor = data.get("cursor")
            if not cursor:
                break

        logger.info("event_scan_complete")

    async def scan_series(self) -> None:
        """Discover and store series metadata from known markets."""
        # Get unique series tickers from the markets table
        async with get_connection(self._config.postgres) as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT DISTINCT series_ticker FROM markets")
                rows = await cur.fetchall()
                series_tickers = [r[0] for r in rows]

        for ticker in series_tickers:
            try:
                data = await self._client.get_series(ticker)
                series = data.get("series", data)
                await self._upsert_series(ticker, series)
            except Exception:
                logger.exception("series_fetch_error", ticker=ticker)

        logger.info("series_scan_complete", count=len(series_tickers))

    async def run(self) -> None:
        """Main polling loop."""
        logger.info("market_scanner_started", interval=self._config.tuning.market_scan_interval)

        while True:
            try:
                await self.scan_all_markets()
                await self.scan_events()
                await self.scan_series()
            except Exception:
                logger.exception("scan_cycle_error")

            await asyncio.sleep(self._config.tuning.market_scan_interval)

    # ── Database upserts ──────────────────────────────────────────────

    async def _upsert_markets(self, markets: list[KalshiMarket]) -> None:
        """Upsert market metadata into the markets table."""
        if not markets:
            return

        async with get_connection(self._config.postgres) as conn:
            async with conn.cursor() as cur:
                for m in markets:
                    row = m.to_db_row()
                    await cur.execute(
                        """
                        INSERT INTO markets (ticker, event_ticker, series_ticker, title,
                                             subtitle, status, market_type, close_time, result,
                                             last_synced_at)
                        VALUES (%(ticker)s, %(event_ticker)s, %(series_ticker)s, %(title)s,
                                %(subtitle)s, %(status)s, %(market_type)s, %(close_time)s,
                                %(result)s, NOW())
                        ON CONFLICT (ticker) DO UPDATE SET
                            status = EXCLUDED.status,
                            close_time = EXCLUDED.close_time,
                            result = EXCLUDED.result,
                            last_synced_at = NOW()
                        """,
                        row,
                    )
            await conn.commit()

    async def _upsert_events(self, events: list[dict]) -> None:
        """Upsert event metadata."""
        async with get_connection(self._config.postgres) as conn:
            async with conn.cursor() as cur:
                for e in events:
                    await cur.execute(
                        """
                        INSERT INTO events (ticker, series_ticker, title, status,
                                            market_count, last_synced_at)
                        VALUES (%(event_ticker)s, %(series_ticker)s, %(title)s,
                                %(status)s, %(mutually_exclusive)s, NOW())
                        ON CONFLICT (ticker) DO UPDATE SET
                            status = EXCLUDED.status,
                            market_count = EXCLUDED.market_count,
                            last_synced_at = NOW()
                        """,
                        {
                            "event_ticker": e.get("event_ticker", ""),
                            "series_ticker": e.get("series_ticker", ""),
                            "title": e.get("title", ""),
                            "status": e.get("status", ""),
                            "mutually_exclusive": len(e.get("markets", [])),
                        },
                    )
            await conn.commit()

    async def _upsert_series(self, ticker: str, series: dict) -> None:
        """Upsert a single series."""
        async with get_connection(self._config.postgres) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO series (ticker, title, category, tags, last_synced_at)
                    VALUES (%(ticker)s, %(title)s, %(category)s, %(tags)s, NOW())
                    ON CONFLICT (ticker) DO UPDATE SET
                        title = EXCLUDED.title,
                        category = EXCLUDED.category,
                        tags = EXCLUDED.tags,
                        last_synced_at = NOW()
                    """,
                    {
                        "ticker": ticker,
                        "title": series.get("title", ""),
                        "category": series.get("category", ""),
                        "tags": series.get("tags", []),
                    },
                )
            await conn.commit()


async def main() -> None:
    """Entry point for the market scanner process."""
    import structlog

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
    )

    config = get_config()
    auth = KalshiWSAuth(
        key_id=config.kalshi.api_key_id,
        private_key_path=str(config.kalshi.private_key_path),
    )
    rest_client = KalshiRESTClient(auth, config.kalshi.api_base_url)
    scanner = MarketScanner(rest_client, config)

    try:
        await scanner.run()
    finally:
        await rest_client.close()


if __name__ == "__main__":
    asyncio.run(main())
