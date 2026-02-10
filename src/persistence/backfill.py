"""REST-based gap filling for detected data gaps."""

from __future__ import annotations

import asyncio
from datetime import datetime

import structlog

from src.config import AppConfig
from src.ingestion.rest_client import KalshiRESTClient
from src.models import KalshiTrade
from src.persistence.db import get_connection

logger = structlog.get_logger(__name__)


class Backfiller:
    """
    Uses Kalshi REST API to fill data gaps detected by GapDetector.
    """

    def __init__(self, rest_client: KalshiRESTClient, config: AppConfig) -> None:
        self._client = rest_client
        self._config = config

    async def backfill_trades(
        self,
        market_ticker: str,
        start: datetime,
        end: datetime,
    ) -> int:
        """
        Fetch trades via REST API for a given time range and insert into DB.
        Returns count of backfilled records.
        """
        total = 0
        cursor: str | None = None
        min_ts = int(start.timestamp())
        max_ts = int(end.timestamp())

        while True:
            try:
                data = await self._client.get_trades(
                    ticker=market_ticker,
                    cursor=cursor,
                    limit=200,
                    min_ts=min_ts,
                    max_ts=max_ts,
                )
            except Exception:
                logger.exception(
                    "backfill_fetch_error",
                    market_ticker=market_ticker,
                )
                break

            trades_raw = data.get("trades", [])
            if not trades_raw:
                break

            trades = []
            for t in trades_raw:
                try:
                    trade = KalshiTrade.model_validate(t)
                    trades.append(trade)
                except Exception:
                    logger.exception("backfill_trade_parse_error", raw=t)

            if trades:
                await self._insert_trades(trades)
                total += len(trades)

            cursor = data.get("cursor")
            if not cursor:
                break

            # Small delay to respect rate limits
            await asyncio.sleep(0.5)

        logger.info(
            "backfill_complete",
            market_ticker=market_ticker,
            start=start.isoformat(),
            end=end.isoformat(),
            records=total,
        )
        return total

    async def backfill_candlesticks(
        self,
        series_ticker: str,
        market_ticker: str,
        period_interval: int = 60,
    ) -> int:
        """
        Fetch candlestick data as a fallback when trade-level data isn't available.
        """
        try:
            data = await self._client.get_candlesticks(
                series_ticker=series_ticker,
                ticker=market_ticker,
                period_interval=period_interval,
            )
        except Exception:
            logger.exception(
                "backfill_candlestick_error",
                market_ticker=market_ticker,
            )
            return 0

        candles = data.get("candlesticks", [])
        logger.info(
            "candlestick_backfill",
            market_ticker=market_ticker,
            candles=len(candles),
        )
        return len(candles)

    async def _insert_trades(self, trades: list[KalshiTrade]) -> None:
        """Insert backfilled trades with deduplication."""
        async with get_connection(self._config.postgres) as conn:
            async with conn.cursor() as cur:
                for trade in trades:
                    row = trade.to_db_row()
                    await cur.execute(
                        """
                        INSERT INTO trades (ts, trade_id, market_ticker, yes_price,
                                            no_price, count, taker_side)
                        VALUES (%(ts)s, %(trade_id)s, %(market_ticker)s, %(yes_price)s,
                                %(no_price)s, %(count)s, %(taker_side)s)
                        ON CONFLICT DO NOTHING
                        """,
                        row,
                    )
            await conn.commit()

    async def backfill_gaps(
        self,
        gaps: dict[str, list[tuple[datetime, datetime]]],
    ) -> dict[str, int]:
        """Backfill all detected gaps. Returns count per market."""
        results: dict[str, int] = {}

        for ticker, gap_ranges in gaps.items():
            total = 0
            for gap_start, gap_end in gap_ranges:
                count = await self.backfill_trades(ticker, gap_start, gap_end)
                total += count
            results[ticker] = total

        logger.info(
            "gap_backfill_complete",
            markets=len(results),
            total_records=sum(results.values()),
        )
        return results
