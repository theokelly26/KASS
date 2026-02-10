"""kass tail <stream> -- Tail a Redis stream in real time.

Shows the last N messages then follows new ones, pretty-printing the JSON payload.

Streams:
    trades, ticker, orderbook_deltas, orderbook_snapshots, lifecycle, system,
    signals_all, signals_composite, signals_flow, signals_oi, signals_regime,
    signals_crossmarket, signals_lifecycle
"""

from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.live import Live
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from src.cli.display import console


# Map of short stream names to full Redis stream keys.
STREAM_MAP: dict[str, str] = {
    "trades": "kalshi:trades",
    "ticker": "kalshi:ticker_v2",
    "orderbook_deltas": "kalshi:orderbook:deltas",
    "orderbook_snapshots": "kalshi:orderbook:snapshots",
    "lifecycle": "kalshi:lifecycle",
    "system": "kalshi:system",
    "signals_all": "kalshi:signals:all",
    "signals_composite": "kalshi:signals:composite",
    "signals_flow": "kalshi:signals:flow_toxicity",
    "signals_oi": "kalshi:signals:oi_divergence",
    "signals_regime": "kalshi:signals:regime",
    "signals_crossmarket": "kalshi:signals:cross_market",
    "signals_lifecycle": "kalshi:signals:lifecycle",
}


def _list_streams() -> None:
    """Print available stream names."""
    table = Table(title="Available Streams", show_lines=False, pad_edge=True)
    table.add_column("Name", style="bold")
    table.add_column("Redis Key", style="dim")
    for name, key in STREAM_MAP.items():
        table.add_row(name, key)
    console.print(table)


def _pretty_payload(msg_id: str, fields: dict) -> Panel:
    """Create a rich Panel for one stream message."""
    import json

    data_raw = fields.get("data", "{}")
    try:
        parsed = json.loads(data_raw)
        formatted = json.dumps(parsed, indent=2, default=str)
    except (json.JSONDecodeError, TypeError):
        formatted = str(data_raw)

    syntax = Syntax(formatted, "json", theme="monokai", word_wrap=True)
    return Panel(syntax, title=f"[dim]{msg_id}[/dim]", expand=False, border_style="dim")


# ---------------------------------------------------------------------------
# Core tail logic
# ---------------------------------------------------------------------------

async def _tail_stream(config, stream_key: str, count: int) -> None:
    from src.cache.redis_client import get_redis, close_redis

    redis = await get_redis(config.redis)

    # 1) Show last N messages via XREVRANGE
    console.print(f"[bold cyan]Stream:[/bold cyan] {stream_key}")
    try:
        length = await redis.xlen(stream_key)
        console.print(f"[dim]Stream length: {length}[/dim]")
    except Exception:
        console.print("[dim]Could not determine stream length.[/dim]")

    console.print(f"[dim]Showing last {count} messages, then following new ones...[/dim]")
    console.print()

    try:
        history = await redis.xrevrange(stream_key, count=count)
    except Exception as e:
        console.print(f"[red]Cannot read stream:[/red] {e}")
        await close_redis()
        return

    # XREVRANGE returns newest first; reverse for chronological display.
    history.reverse()
    for msg_id, fields in history:
        console.print(_pretty_payload(msg_id, fields))

    if history:
        last_id = history[-1][0]
    else:
        last_id = "$"

    # 2) Follow new messages via XREAD in a loop
    console.print()
    console.print("[bold cyan]--- live tail (Ctrl+C to stop) ---[/bold cyan]")
    console.print()

    try:
        while True:
            try:
                results = await redis.xread(
                    {stream_key: last_id}, count=50, block=1000
                )
            except Exception:
                await asyncio.sleep(1)
                continue

            if not results:
                continue

            for _stream_name, messages in results:
                for msg_id, fields in messages:
                    last_id = msg_id
                    console.print(_pretty_payload(msg_id, fields))

    except KeyboardInterrupt:
        console.print("\n[dim]Tail stopped.[/dim]")
    finally:
        await close_redis()


# ---------------------------------------------------------------------------
# Main command
# ---------------------------------------------------------------------------

async def _tail_async(stream: str, count: int) -> None:
    from src.config import get_config

    config = get_config()

    # Resolve stream name
    stream_key = STREAM_MAP.get(stream)
    if stream_key is None:
        # Allow passing the raw Redis key directly
        if ":" in stream:
            stream_key = stream
        else:
            console.print(f"[red]Unknown stream:[/red] '{stream}'")
            console.print()
            _list_streams()
            return

    await _tail_stream(config, stream_key, count)


def tail(
    stream: str = typer.Argument(
        ...,
        help="Stream name (e.g. trades, signals_all) or full Redis key",
    ),
    count: int = typer.Option(10, "--count", "-n", help="Number of historical messages to show"),
) -> None:
    """Tail a Redis stream: show last N messages then follow in real time."""
    asyncio.run(_tail_async(stream, count))
