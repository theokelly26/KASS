"""kass markets -- Market activity overview.

Usage:
    kass markets
    kass markets --sort volume
    kass markets --sort signals --limit 20
"""

from __future__ import annotations

import asyncio
from typing import Optional

import typer

from src.cli.display import (
    console,
    create_market_table,
    format_price,
    format_regime,
)


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

async def _fetch_markets(config, sort: str, limit: int) -> list[dict]:
    """
    Build a market overview by joining:
      - Latest price from price_snapshots
      - Latest regime from regime_log
      - Signal count (last 24h) from signal_log
    """
    from src.persistence.db import get_connection

    # Using DISTINCT ON to get the latest row per market for each source,
    # then joining them together.
    sql = """
        WITH latest_price AS (
            SELECT DISTINCT ON (market_ticker)
                market_ticker,
                yes_price,
                spread,
                volume_24h,
                open_interest,
                ts AS price_ts
            FROM price_snapshots
            ORDER BY market_ticker, ts DESC
        ),
        latest_regime AS (
            SELECT DISTINCT ON (market_ticker)
                market_ticker,
                new_regime AS regime
            FROM regime_log
            ORDER BY market_ticker, ts DESC
        ),
        signal_counts AS (
            SELECT
                market_ticker,
                count(*) AS signal_count
            FROM signal_log
            WHERE ts > now() - interval '24 hours'
            GROUP BY market_ticker
        )
        SELECT
            lp.market_ticker,
            lp.yes_price,
            lp.spread,
            lp.volume_24h,
            lp.open_interest,
            lr.regime,
            COALESCE(sc.signal_count, 0) AS signal_count
        FROM latest_price lp
        LEFT JOIN latest_regime lr ON lr.market_ticker = lp.market_ticker
        LEFT JOIN signal_counts sc ON sc.market_ticker = lp.market_ticker
        ORDER BY
            CASE %s
                WHEN 'volume'  THEN COALESCE(lp.volume_24h, 0)
                WHEN 'signals' THEN COALESCE(sc.signal_count, 0)
                ELSE COALESCE(lp.volume_24h, 0)
            END DESC
        LIMIT %s
    """

    rows: list[dict] = []
    async with get_connection(config.postgres) as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, (sort, limit))
            for row in await cur.fetchall():
                rows.append(
                    {
                        "ticker": row[0],
                        "yes_price": row[1],
                        "spread": row[2],
                        "volume_24h": row[3],
                        "open_interest": row[4],
                        "regime": row[5],
                        "signal_count": row[6],
                    }
                )
    return rows


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _render(rows: list[dict], sort: str) -> None:
    if not rows:
        console.print("[dim]No market data found.[/dim]")
        return

    table = create_market_table(title=f"Market Overview (sorted by {sort})")
    for r in rows:
        table.add_row(
            r["ticker"],
            format_price(r["yes_price"]),
            format_price(r["spread"]) if r["spread"] is not None else "--",
            str(r["volume_24h"]) if r["volume_24h"] is not None else "--",
            str(r["open_interest"]) if r["open_interest"] is not None else "--",
            format_regime(r["regime"]),
            str(r["signal_count"]),
        )
    console.print(table)


# ---------------------------------------------------------------------------
# Main command
# ---------------------------------------------------------------------------

async def _markets_async(sort: str, limit: int) -> None:
    from src.config import get_config
    from src.persistence.db import close_pool

    config = get_config()
    try:
        rows = await _fetch_markets(config, sort, limit)
    except Exception as e:
        console.print(f"[red]Query failed:[/red] {e}")
        return
    finally:
        await close_pool()

    _render(rows, sort)


def markets(
    sort: str = typer.Option(
        "volume",
        "--sort",
        "-s",
        help="Sort by: volume, signals, regime",
    ),
    limit: int = typer.Option(30, "--limit", "-n", help="Number of markets to display"),
) -> None:
    """Market activity overview: prices, volumes, regimes, and signal counts."""
    asyncio.run(_markets_async(sort, limit))
