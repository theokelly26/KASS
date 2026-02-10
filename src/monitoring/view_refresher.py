"""Periodically refreshes materialized views used for analysis."""

from __future__ import annotations

import asyncio

import structlog

from src.config import AppConfig, get_config
from src.persistence.db import get_connection

logger = structlog.get_logger(__name__)

REFRESH_INTERVAL = 900  # 15 minutes

VIEWS_TO_REFRESH = [
    "signal_outcomes",
    "market_latest",
]


class ViewRefresher:
    """Refreshes materialized views on a schedule."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    async def run(self) -> None:
        logger.info("view_refresher_started", interval=REFRESH_INTERVAL, views=VIEWS_TO_REFRESH)

        while True:
            await asyncio.sleep(REFRESH_INTERVAL)
            for view in VIEWS_TO_REFRESH:
                try:
                    async with get_connection(self._config.postgres) as conn:
                        await conn.set_autocommit(True)
                        async with conn.cursor() as cur:
                            await cur.execute(
                                f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"
                            )
                    logger.info("view_refreshed", view=view)
                except Exception:
                    logger.exception("view_refresh_error", view=view)


async def main() -> None:
    """Entry point for the view refresher."""
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
    refresher = ViewRefresher(config)
    await refresher.run()


if __name__ == "__main__":
    asyncio.run(main())
