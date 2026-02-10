"""kass market <ticker> -- Deep dive on a single market.

Shows market metadata, current price, recent signals, composites, and trades.
"""

from __future__ import annotations

import asyncio

import typer
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.cli.display import (
    console,
    create_signal_table,
    create_trade_table,
    format_direction,
    format_float,
    format_price,
    format_regime,
    format_ts,
)


# ---------------------------------------------------------------------------
# Data fetching helpers
# ---------------------------------------------------------------------------

async def _fetch_market_info(conn, ticker: str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT ticker, event_ticker, series_ticker, title, subtitle,
                   status, market_type, close_time, result
            FROM markets
            WHERE ticker = %s
            """,
            (ticker,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "ticker": row[0],
            "event_ticker": row[1],
            "series_ticker": row[2],
            "title": row[3],
            "subtitle": row[4],
            "status": row[5],
            "market_type": row[6],
            "close_time": row[7],
            "result": row[8],
        }


async def _fetch_latest_price(conn, ticker: str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT yes_price, yes_bid, yes_ask, spread, volume_24h, open_interest, ts
            FROM price_snapshots
            WHERE market_ticker = %s
            ORDER BY ts DESC
            LIMIT 1
            """,
            (ticker,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "yes_price": row[0],
            "yes_bid": row[1],
            "yes_ask": row[2],
            "spread": row[3],
            "volume_24h": row[4],
            "open_interest": row[5],
            "ts": row[6],
        }


async def _fetch_recent_signals(conn, ticker: str, limit: int = 20) -> list[dict]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT ts, signal_type, direction, strength, confidence, urgency
            FROM signal_log
            WHERE market_ticker = %s
            ORDER BY ts DESC
            LIMIT %s
            """,
            (ticker, limit),
        )
        return [
            {
                "ts": r[0],
                "signal_type": r[1],
                "direction": r[2],
                "strength": r[3],
                "confidence": r[4],
                "urgency": r[5],
            }
            for r in await cur.fetchall()
        ]


async def _fetch_latest_composite(conn, ticker: str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT ts, direction, composite_score, regime,
                   active_signal_count
            FROM composite_log
            WHERE market_ticker = %s
            ORDER BY ts DESC
            LIMIT 1
            """,
            (ticker,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "ts": row[0],
            "direction": row[1],
            "composite_score": row[2],
            "regime": row[3],
            "active_signal_count": row[4],
        }


async def _fetch_recent_trades(conn, ticker: str, limit: int = 10) -> list[dict]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT ts, yes_price, count, taker_side, trade_id
            FROM trades
            WHERE market_ticker = %s
            ORDER BY ts DESC
            LIMIT %s
            """,
            (ticker, limit),
        )
        return [
            {
                "ts": r[0],
                "yes_price": r[1],
                "count": r[2],
                "taker_side": r[3],
                "trade_id": r[4],
            }
            for r in await cur.fetchall()
        ]


async def _fetch_latest_regime(conn, ticker: str) -> dict | None:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT ts, old_regime, new_regime, trade_rate, message_rate, depth_imbalance
            FROM regime_log
            WHERE market_ticker = %s
            ORDER BY ts DESC
            LIMIT 1
            """,
            (ticker,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "ts": row[0],
            "old_regime": row[1],
            "new_regime": row[2],
            "trade_rate": row[3],
            "message_rate": row[4],
            "depth_imbalance": row[5],
        }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _render_info(info: dict, price: dict | None, regime: dict | None) -> Panel:
    table = Table(show_header=False, show_edge=False, pad_edge=True)
    table.add_column("Label", style="bold", width=20)
    table.add_column("Value")

    table.add_row("Ticker", info["ticker"])
    table.add_row("Title", info["title"] or "--")
    table.add_row("Subtitle", info["subtitle"] or "--")
    table.add_row("Event", info["event_ticker"])
    table.add_row("Series", info["series_ticker"])
    table.add_row("Status", info["status"])
    table.add_row("Type", info["market_type"] or "--")
    table.add_row("Close time", format_ts(info["close_time"]))
    table.add_row("Result", info["result"] or "--")

    if price:
        table.add_row("", "")  # spacer
        table.add_row("Yes price", format_price(price["yes_price"]))
        table.add_row("Bid / Ask", f"{format_price(price['yes_bid'])} / {format_price(price['yes_ask'])}")
        table.add_row("Spread", format_price(price["spread"]))
        table.add_row("Volume 24h", str(price["volume_24h"]) if price["volume_24h"] is not None else "--")
        table.add_row("Open interest", str(price["open_interest"]) if price["open_interest"] is not None else "--")
        table.add_row("Price as of", format_ts(price["ts"]))

    if regime:
        table.add_row("", "")
        table.add_row("Regime", format_regime(regime["new_regime"]))
        table.add_row("Prev regime", format_regime(regime["old_regime"]))
        table.add_row("Trade rate", format_float(regime["trade_rate"]))
        table.add_row("Msg rate", format_float(regime["message_rate"]))
        table.add_row("Depth imbal", format_float(regime["depth_imbalance"]))
        table.add_row("Regime as of", format_ts(regime["ts"]))

    return Panel(table, title=f"[bold]{info['ticker']}[/bold]", expand=False)


def _render_composite(comp: dict | None) -> Panel:
    if comp is None:
        return Panel("[dim]No composite signal recorded yet.[/dim]", title="Latest Composite", expand=False)

    table = Table(show_header=False, show_edge=False, pad_edge=True)
    table.add_column("Label", style="bold", width=20)
    table.add_column("Value")
    table.add_row("Direction", format_direction(comp["direction"]))
    table.add_row("Score", format_float(comp["composite_score"], 3))
    table.add_row("Regime", format_regime(comp["regime"]))
    table.add_row("Active signals", str(comp["active_signal_count"]))
    table.add_row("Computed at", format_ts(comp["ts"]))
    return Panel(table, title="Latest Composite", expand=False)


def _render_signals(signals_list: list[dict]) -> None:
    if not signals_list:
        console.print("[dim]No signals recorded for this market.[/dim]")
        return

    table = create_signal_table(title=f"Recent Signals ({len(signals_list)})")
    for s in signals_list:
        urgency = s["urgency"] or ""
        urg_style = "bold yellow" if urgency == "immediate" else (
            "cyan" if urgency == "watch" else "dim"
        )
        table.add_row(
            format_ts(s["ts"]),
            s["signal_type"],
            "--",  # market already known from context
            format_direction(s["direction"]),
            format_float(s["strength"]),
            format_float(s["confidence"]),
            Text(urgency, style=urg_style),
        )
    console.print(table)


def _render_trades(trades: list[dict]) -> None:
    if not trades:
        console.print("[dim]No trades recorded for this market.[/dim]")
        return

    table = create_trade_table(title=f"Recent Trades ({len(trades)})")
    for t in trades:
        side = t["taker_side"] or ""
        side_style = "green" if "yes" in side.lower() else ("red" if "no" in side.lower() else "dim")
        table.add_row(
            format_ts(t["ts"]),
            format_price(t["yes_price"]),
            str(t["count"]),
            Text(side, style=side_style),
            str(t["trade_id"])[:20] if t["trade_id"] else "--",
        )
    console.print(table)


# ---------------------------------------------------------------------------
# Main command
# ---------------------------------------------------------------------------

async def _market_async(ticker: str) -> None:
    from src.config import get_config
    from src.persistence.db import get_connection, close_pool

    config = get_config()
    try:
        async with get_connection(config.postgres) as conn:
            info = await _fetch_market_info(conn, ticker)
            if not info:
                console.print(f"[red]Market '{ticker}' not found in the markets table.[/red]")
                return

            price = await _fetch_latest_price(conn, ticker)
            regime = await _fetch_latest_regime(conn, ticker)
            recent_signals = await _fetch_recent_signals(conn, ticker)
            composite = await _fetch_latest_composite(conn, ticker)
            trades = await _fetch_recent_trades(conn, ticker)

        # Render everything
        console.print()
        console.print(_render_info(info, price, regime))
        console.print()
        console.print(_render_composite(composite))
        console.print()
        _render_signals(recent_signals)
        console.print()
        _render_trades(trades)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
    finally:
        await close_pool()


def market(
    ticker: str = typer.Argument(..., help="Market ticker (e.g. KXBTCD-25MAR14-T52000)"),
) -> None:
    """Deep dive on a single market: info, price, signals, composites, trades."""
    asyncio.run(_market_async(ticker.upper()))
