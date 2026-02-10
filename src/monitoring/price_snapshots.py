"""Periodic price snapshot service for signal validation.

Reads current prices from Redis state cache and writes to price_snapshots table
every 30 seconds. These snapshots are used to evaluate signal accuracy after the fact.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import orjson
import structlog

from src.cache.redis_client import get_redis
from src.cache.state import KEY_ORDERBOOK, KEY_TICKER
from src.config import AppConfig, get_config
from src.persistence.db import get_connection

logger = structlog.get_logger(__name__)

SNAPSHOT_INTERVAL = 30  # seconds


class PriceSnapshotService:
    """Takes periodic price snapshots for all active markets."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._total_snapshots = 0

    async def run(self) -> None:
        logger.info("price_snapshot_service_started", interval=SNAPSHOT_INTERVAL)
        redis = await get_redis(self._config.redis)

        while True:
            try:
                await self._take_snapshots(redis)
            except Exception:
                logger.exception("snapshot_cycle_error")
            await asyncio.sleep(SNAPSHOT_INTERVAL)

    async def _take_snapshots(self, redis) -> None:
        # Get active market tickers from DB (markets with recent trades)
        tickers = await self._get_active_tickers()
        if not tickers:
            logger.debug("no_markets_for_snapshots")
            return

        now = datetime.now(tz=timezone.utc)
        rows = []

        for ticker in tickers:
            try:
                snapshot = await self._build_snapshot(redis, ticker, now)
                if snapshot:
                    rows.append(snapshot)
            except Exception:
                logger.debug("snapshot_build_error", ticker=ticker)

        if rows:
            await self._flush(rows)
            self._total_snapshots += len(rows)
            logger.debug("snapshots_taken", count=len(rows), total=self._total_snapshots)

    async def _get_active_tickers(self) -> list[str]:
        """Get market tickers with recent activity from the database."""
        try:
            async with get_connection(self._config.postgres) as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT DISTINCT market_ticker
                        FROM trades
                        WHERE ts > NOW() - INTERVAL '4 hours'
                        ORDER BY market_ticker
                        """
                    )
                    rows = await cur.fetchall()
                    return [row[0] for row in rows]
        except Exception:
            logger.exception("active_tickers_query_error")
            return []

    async def _build_snapshot(self, redis, ticker: str, now: datetime) -> dict | None:
        """Build a price snapshot from Redis state for a single market."""
        # Try to get ticker state (last price from ticker_v2 updates)
        ticker_key = KEY_TICKER.format(ticker=ticker)
        ticker_raw = await redis.get(ticker_key)

        yes_price = None
        volume_24h = None
        open_interest = None

        if ticker_raw:
            try:
                ticker_data = orjson.loads(ticker_raw)
                yes_price = ticker_data.get("price")
                volume_24h = ticker_data.get("volume")
                open_interest = ticker_data.get("open_interest")
            except Exception:
                pass

        # Try to get orderbook state for bid/ask/spread
        ob_key = KEY_ORDERBOOK.format(ticker=ticker)
        ob_raw = await redis.get(ob_key)

        yes_bid = None
        yes_ask = None
        spread = None

        if ob_raw:
            try:
                book = orjson.loads(ob_raw)
                yes_levels = book.get("yes", {})
                no_levels = book.get("no", {})

                if yes_levels:
                    yes_bid = max(int(p) for p in yes_levels.keys())
                if no_levels:
                    best_no_bid = max(int(p) for p in no_levels.keys())
                    yes_ask = 100 - best_no_bid

                if yes_bid is not None and yes_ask is not None:
                    spread = yes_ask - yes_bid
            except Exception:
                pass

        # If we have a price from ticker state, use it; otherwise try midpoint
        if yes_price is None and yes_bid is not None and yes_ask is not None:
            yes_price = round((yes_bid + yes_ask) / 2)

        # Fallback: get last trade price from DB
        if yes_price is None:
            try:
                async with get_connection(self._config.postgres) as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(
                            """
                            SELECT yes_price FROM trades
                            WHERE market_ticker = %s
                            ORDER BY ts DESC LIMIT 1
                            """,
                            (ticker,),
                        )
                        row = await cur.fetchone()
                        if row:
                            yes_price = row[0]
            except Exception:
                pass

        # Only snapshot if we have at least a price
        if yes_price is None:
            return None

        return {
            "ts": now,
            "market_ticker": ticker,
            "yes_price": yes_price,
            "yes_bid": yes_bid,
            "yes_ask": yes_ask,
            "spread": spread,
            "volume_24h": volume_24h,
            "open_interest": open_interest,
        }

    async def _flush(self, rows: list[dict]) -> None:
        retries = 0
        while retries < 3:
            try:
                async with get_connection(self._config.postgres) as conn:
                    async with conn.cursor() as cur:
                        for row in rows:
                            await cur.execute(
                                """
                                INSERT INTO price_snapshots (ts, market_ticker, yes_price,
                                    yes_bid, yes_ask, spread, volume_24h, open_interest)
                                VALUES (%(ts)s, %(market_ticker)s, %(yes_price)s,
                                    %(yes_bid)s, %(yes_ask)s, %(spread)s,
                                    %(volume_24h)s, %(open_interest)s)
                                """,
                                row,
                            )
                    await conn.commit()
                return
            except Exception:
                retries += 1
                logger.exception("snapshot_flush_error", retry=retries)
                await asyncio.sleep(2 ** retries)

        logger.error("snapshot_flush_failed_permanently", count=len(rows))


async def main() -> None:
    """Entry point for the price snapshot service."""
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
    service = PriceSnapshotService(config)
    await service.run()


if __name__ == "__main__":
    asyncio.run(main())
