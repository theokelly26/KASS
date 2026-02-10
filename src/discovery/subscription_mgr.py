"""Dynamic WebSocket subscription manager.

Coordinates with MarketScanner to add/remove orderbook subscriptions
based on market activity levels.
"""

from __future__ import annotations

import structlog

from src.ingestion.ws_client import KalshiWSManager
from src.persistence.db import get_connection
from src.config import PostgresConfig

logger = structlog.get_logger(__name__)


class SubscriptionManager:
    """
    Manages which markets the WebSocket is subscribed to.

    Strategy:
    - ticker_v2: subscribe to ALL markets (no filter needed)
    - trade: subscribe to ALL markets (no filter needed)
    - orderbook_delta: subscribe to "active" markets only
    - market_lifecycle_v2: subscribe to ALL
    """

    def __init__(
        self,
        ws_manager: KalshiWSManager,
        pg_config: PostgresConfig,
    ) -> None:
        self._ws = ws_manager
        self._pg_config = pg_config
        self._orderbook_sid: int | None = None
        self._active_ob_tickers: set[str] = set()

    async def initialize(self) -> None:
        """Set up initial subscriptions for broadcast channels."""
        # These subscribe to all markets without filtering
        await self._ws.subscribe(["ticker_v2"])
        await self._ws.subscribe(["trade"])
        await self._ws.subscribe(["market_lifecycle_v2"])
        logger.info("broadcast_subscriptions_initialized")

    async def on_markets_discovered(self, new_markets: list[str]) -> None:
        """Called when scanner finds new markets. Subscribe to orderbook if active."""
        active = await self._filter_active(new_markets)
        if not active:
            return

        if self._orderbook_sid is None:
            self._orderbook_sid = await self._ws.subscribe(
                ["orderbook_delta"], market_tickers=active
            )
        else:
            await self._ws.update_subscription(
                self._orderbook_sid, add_tickers=active
            )

        self._active_ob_tickers.update(active)
        logger.info("orderbook_subscriptions_added", count=len(active))

    async def on_markets_closed(self, closed_markets: list[str]) -> None:
        """Called when markets close/settle. Unsubscribe from orderbook."""
        to_remove = [t for t in closed_markets if t in self._active_ob_tickers]
        if not to_remove or self._orderbook_sid is None:
            return

        await self._ws.update_subscription(
            self._orderbook_sid, remove_tickers=to_remove
        )
        self._active_ob_tickers -= set(to_remove)
        logger.info("orderbook_subscriptions_removed", count=len(to_remove))

    async def get_active_orderbook_tickers(self) -> list[str]:
        """
        Determine which markets warrant orderbook subscriptions.
        Criteria: volume > 0 in last 24h, or market opens within 48h.
        """
        async with get_connection(self._pg_config) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT DISTINCT m.ticker
                    FROM markets m
                    WHERE m.status = 'open'
                      AND (
                        -- Has recent volume
                        EXISTS (
                            SELECT 1 FROM trades t
                            WHERE t.market_ticker = m.ticker
                              AND t.ts > NOW() - INTERVAL '24 hours'
                        )
                        OR
                        -- Closes within 48 hours
                        (m.close_time IS NOT NULL AND m.close_time < NOW() + INTERVAL '48 hours')
                      )
                    """
                )
                return [row[0] for row in await cur.fetchall()]

    async def reconcile(self) -> None:
        """
        Periodically ensure subscriptions match desired state.
        Add missing subs, remove stale ones.
        """
        desired = set(await self.get_active_orderbook_tickers())
        current = self._active_ob_tickers

        to_add = list(desired - current)
        to_remove = list(current - desired)

        if to_add:
            await self.on_markets_discovered(to_add)
        if to_remove:
            await self.on_markets_closed(to_remove)

        if to_add or to_remove:
            logger.info(
                "subscriptions_reconciled",
                added=len(to_add),
                removed=len(to_remove),
                total=len(self._active_ob_tickers),
            )

    async def _filter_active(self, tickers: list[str]) -> list[str]:
        """Filter tickers to only those that should get orderbook subscriptions."""
        if not tickers:
            return []

        async with get_connection(self._pg_config) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT ticker FROM markets
                    WHERE ticker = ANY(%s)
                      AND status = 'open'
                      AND (
                          close_time IS NULL
                          OR close_time > NOW()
                      )
                    """,
                    (tickers,),
                )
                return [row[0] for row in await cur.fetchall()]
