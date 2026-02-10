"""kass signals -- View recent or live signals.

Usage:
    kass signals                     # last 50 signals from DB
    kass signals --live              # live stream from Redis
    kass signals --type flow_toxicity
    kass signals --market TICKER
"""

from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.live import Live
from rich.text import Text

from src.cli.display import (
    console,
    create_signal_table,
    format_direction,
    format_float,
    format_ts,
)


# ---------------------------------------------------------------------------
# DB query: recent signals
# ---------------------------------------------------------------------------

async def _query_recent_signals(
    config,
    limit: int,
    signal_type: str | None,
    market_ticker: str | None,
) -> list[dict]:
    from src.persistence.db import get_connection

    clauses: list[str] = []
    params: list = []
    idx = 1

    if signal_type:
        clauses.append(f"signal_type = ${idx}")
        params.append(signal_type)
        idx += 1
    if market_ticker:
        clauses.append(f"market_ticker = ${idx}")
        params.append(market_ticker)
        idx += 1

    where = ""
    if clauses:
        where = "WHERE " + " AND ".join(clauses)

    sql = f"""
        SELECT ts, signal_type, market_ticker, direction,
               strength, confidence, urgency
        FROM signal_log
        {where}
        ORDER BY ts DESC
        LIMIT {limit}
    """

    rows: list[dict] = []
    async with get_connection(config.postgres) as conn:
        # psycopg3 uses %s for placeholders; build safely
        # We need to use psycopg3 parameterised queries with %s style
        real_clauses: list[str] = []
        real_params: list = []
        if signal_type:
            real_clauses.append("signal_type = %s")
            real_params.append(signal_type)
        if market_ticker:
            real_clauses.append("market_ticker = %s")
            real_params.append(market_ticker)

        real_where = ""
        if real_clauses:
            real_where = "WHERE " + " AND ".join(real_clauses)

        real_sql = f"""
            SELECT ts, signal_type, market_ticker, direction,
                   strength, confidence, urgency
            FROM signal_log
            {real_where}
            ORDER BY ts DESC
            LIMIT %s
        """
        real_params.append(limit)

        async with conn.cursor() as cur:
            await cur.execute(real_sql, real_params)
            for row in await cur.fetchall():
                rows.append(
                    {
                        "ts": row[0],
                        "signal_type": row[1],
                        "market_ticker": row[2],
                        "direction": row[3],
                        "strength": row[4],
                        "confidence": row[5],
                        "urgency": row[6],
                    }
                )
    return rows


# ---------------------------------------------------------------------------
# Live stream from Redis
# ---------------------------------------------------------------------------

async def _live_signal_stream(
    config,
    signal_type: str | None,
    market_ticker: str | None,
) -> None:
    import orjson
    from src.cache.redis_client import get_redis, close_redis

    redis = await get_redis(config.redis)
    stream = "kalshi:signals:all"
    last_id = "$"  # Only new messages

    console.print(f"[bold cyan]Tailing {stream}[/bold cyan]  (Ctrl+C to stop)")
    if signal_type:
        console.print(f"  filter type = {signal_type}")
    if market_ticker:
        console.print(f"  filter market = {market_ticker}")
    console.print()

    table = create_signal_table(title="Live Signals")
    row_count = 0

    try:
        with Live(table, console=console, refresh_per_second=4) as live:
            while True:
                try:
                    results = await redis.xread(
                        {stream: last_id}, count=50, block=1000
                    )
                except Exception:
                    await asyncio.sleep(1)
                    continue

                if not results:
                    continue

                for _stream_name, messages in results:
                    for msg_id, fields in messages:
                        last_id = msg_id
                        raw = fields.get("data", "{}")
                        try:
                            data = orjson.loads(raw)
                        except Exception:
                            continue

                        # Apply filters
                        if signal_type and data.get("signal_type") != signal_type:
                            continue
                        if market_ticker and data.get("market_ticker") != market_ticker:
                            continue

                        # Keep table at manageable size
                        row_count += 1
                        if row_count > 200:
                            # Rebuild table to avoid unbounded growth
                            table = create_signal_table(title="Live Signals")
                            row_count = 1
                            live.update(table)

                        urgency = data.get("urgency", "")
                        urg_style = "bold yellow" if urgency == "immediate" else (
                            "cyan" if urgency == "watch" else "dim"
                        )

                        table.add_row(
                            str(data.get("ts", ""))[:19],
                            data.get("signal_type", "?"),
                            data.get("market_ticker", "?"),
                            format_direction(data.get("direction")),
                            format_float(data.get("strength")),
                            format_float(data.get("confidence")),
                            Text(urgency, style=urg_style),
                        )
    except KeyboardInterrupt:
        console.print("\n[dim]Stream closed.[/dim]")
    finally:
        await close_redis()


# ---------------------------------------------------------------------------
# Main command
# ---------------------------------------------------------------------------

async def _signals_async(
    live: bool,
    signal_type: str | None,
    market_ticker: str | None,
    limit: int,
) -> None:
    from src.config import get_config
    from src.persistence.db import close_pool

    config = get_config()

    if live:
        await _live_signal_stream(config, signal_type, market_ticker)
        return

    try:
        rows = await _query_recent_signals(config, limit, signal_type, market_ticker)
    except Exception as e:
        console.print(f"[red]Query failed:[/red] {e}")
        return
    finally:
        await close_pool()

    if not rows:
        console.print("[dim]No signals found.[/dim]")
        return

    table = create_signal_table(title=f"Recent Signals (last {len(rows)})")
    for r in rows:
        urgency = r["urgency"] or ""
        urg_style = "bold yellow" if urgency == "immediate" else (
            "cyan" if urgency == "watch" else "dim"
        )
        table.add_row(
            format_ts(r["ts"]),
            r["signal_type"],
            r["market_ticker"],
            format_direction(r["direction"]),
            format_float(r["strength"]),
            format_float(r["confidence"]),
            Text(urgency, style=urg_style),
        )
    console.print(table)


def signals(
    live: bool = typer.Option(False, "--live", "-l", help="Stream signals in real time"),
    signal_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by signal type"),
    market_ticker: Optional[str] = typer.Option(None, "--market", "-m", help="Filter by market ticker"),
    limit: int = typer.Option(50, "--limit", "-n", help="Number of recent signals to show"),
) -> None:
    """View recent signals from the database, or stream live from Redis."""
    asyncio.run(_signals_async(live, signal_type, market_ticker, limit))
