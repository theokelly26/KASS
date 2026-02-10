"""kass status -- System health dashboard.

Shows component health, data freshness, DB/Redis stats, and market counts.
"""

from __future__ import annotations

import asyncio
import subprocess

import typer
from rich.panel import Panel
from rich.table import Table

from src.cli.display import (
    console,
    format_age,
    format_status_str,
    format_ts,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_redis_health(redis) -> list[dict]:
    """Read health:{component} keys from Redis."""
    import orjson

    health_components = [
        "redis",
        "postgres",
        "trade_stream_backlog",
        "ticker_stream_backlog",
        "orderbook_stream_backlog",
        "lifecycle_stream_backlog",
        "disk",
    ]
    results: list[dict] = []
    for comp in health_components:
        raw = await redis.get(f"health:{comp}")
        if raw:
            results.append(orjson.loads(raw))
        else:
            results.append({"component": comp, "status": "unknown", "details": {}})
    return results


async def _get_data_freshness(conn) -> list[dict]:
    """Query MAX(ts) for each core table to show data freshness."""
    tables = [
        "trades",
        "ticker_updates",
        "orderbook_deltas",
        "signal_log",
        "composite_log",
        "regime_log",
        "price_snapshots",
    ]
    results: list[dict] = []
    async with conn.cursor() as cur:
        for tbl in tables:
            try:
                await cur.execute(
                    f"SELECT max(ts), now() - max(ts) FROM {tbl}"  # noqa: S608
                )
                row = await cur.fetchone()
                if row and row[0]:
                    results.append(
                        {"table": tbl, "latest_ts": row[0], "age": row[1]}
                    )
                else:
                    results.append({"table": tbl, "latest_ts": None, "age": None})
            except Exception:
                results.append({"table": tbl, "latest_ts": None, "age": None})
    return results


async def _get_db_size(conn) -> str:
    """Return human-readable database size."""
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT pg_size_pretty(pg_database_size(current_database()))"
        )
        row = await cur.fetchone()
        return row[0] if row else "unknown"


async def _get_redis_info(redis) -> dict:
    """Gather Redis memory stats."""
    info = await redis.info("memory")
    return {
        "used_memory_human": info.get("used_memory_human", "unknown"),
        "used_memory_peak_human": info.get("used_memory_peak_human", "unknown"),
        "connected_clients": (await redis.info("clients")).get(
            "connected_clients", "?"
        ),
    }


async def _get_market_counts(conn) -> list[dict]:
    """Count markets grouped by status."""
    results: list[dict] = []
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT status, count(*) FROM markets GROUP BY status ORDER BY count(*) DESC"
        )
        rows = await cur.fetchall()
        for row in rows:
            results.append({"status": row[0], "count": row[1]})
    return results


async def _get_tracked_market_count(redis) -> int:
    """Count tickers in the meta:markets set."""
    return await redis.scard("meta:markets")


def _get_pm2_status() -> list[dict]:
    """Try to read PM2 process list. Returns empty list if PM2 is not available."""
    try:
        result = subprocess.run(
            ["pm2", "jlist"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []
        import json

        procs = json.loads(result.stdout)
        return [
            {
                "name": p.get("name", "?"),
                "status": p.get("pm2_env", {}).get("status", "unknown"),
                "restarts": p.get("pm2_env", {}).get("restart_time", 0),
                "uptime": p.get("pm2_env", {}).get("pm_uptime", 0),
                "cpu": p.get("monit", {}).get("cpu", 0),
                "mem_mb": round(p.get("monit", {}).get("memory", 0) / 1024 / 1024, 1),
            }
            for p in procs
            if p.get("name", "").startswith("kass-")
        ]
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return []


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _render_component_health(health: list[dict]) -> Table:
    table = Table(title="Component Health", show_lines=False, pad_edge=True)
    table.add_column("Component", style="bold")
    table.add_column("Status", width=8)
    table.add_column("Details", style="dim")

    for h in health:
        details_parts = []
        for k, v in h.get("details", {}).items():
            details_parts.append(f"{k}={v}")
        table.add_row(
            h["component"],
            format_status_str(h["status"]),
            ", ".join(details_parts) if details_parts else "--",
        )
    return table


def _render_pm2_status(procs: list[dict]) -> Table:
    table = Table(title="PM2 Processes", show_lines=False, pad_edge=True)
    table.add_column("Process", style="bold")
    table.add_column("Status", width=10)
    table.add_column("Restarts", justify="right", width=9)
    table.add_column("CPU %", justify="right", width=6)
    table.add_column("Mem MB", justify="right", width=8)

    for p in procs:
        st = p["status"]
        style = "ok" if st == "online" else ("warning" if st == "stopping" else "critical")
        from rich.text import Text

        table.add_row(
            p["name"],
            Text(st.upper(), style=style),
            str(p["restarts"]),
            str(p["cpu"]),
            str(p["mem_mb"]),
        )
    return table


def _render_freshness(freshness: list[dict]) -> Table:
    table = Table(title="Data Freshness", show_lines=False, pad_edge=True)
    table.add_column("Table", style="bold")
    table.add_column("Latest Record", width=19)
    table.add_column("Age", justify="right", width=12)

    for f in freshness:
        age_str = format_age(f["age"])
        # Highlight stale data (> 5 minutes)
        style = ""
        if f["age"] is not None:
            try:
                if f["age"].total_seconds() > 300:
                    style = "yellow"
                if f["age"].total_seconds() > 1800:
                    style = "red"
            except Exception:
                pass
        from rich.text import Text

        table.add_row(
            f["table"],
            format_ts(f["latest_ts"]),
            Text(age_str, style=style) if style else age_str,
        )
    return table


# ---------------------------------------------------------------------------
# Main command
# ---------------------------------------------------------------------------

async def _status_async() -> None:
    from src.config import get_config
    from src.cache.redis_client import get_redis, close_redis
    from src.persistence.db import get_connection, close_pool

    config = get_config()

    console.print(
        Panel("[bold cyan]KASS -- Kalshi Alpha Signal System[/bold cyan]", expand=False)
    )

    try:
        redis = await get_redis(config.redis)
    except Exception as e:
        console.print(f"[red]Cannot connect to Redis:[/red] {e}")
        return

    try:
        # Component health from Redis
        health = await _get_redis_health(redis)
        console.print(_render_component_health(health))
        console.print()

        # PM2 processes
        pm2 = _get_pm2_status()
        if pm2:
            console.print(_render_pm2_status(pm2))
            console.print()
        else:
            console.print("[dim]PM2 not available or no kass- processes running.[/dim]")
            console.print()

        # Data freshness, DB size, market counts -- require Postgres
        try:
            async with get_connection(config.postgres) as conn:
                freshness = await _get_data_freshness(conn)
                console.print(_render_freshness(freshness))
                console.print()

                db_size = await _get_db_size(conn)
                market_counts = await _get_market_counts(conn)
        except Exception as e:
            console.print(f"[red]Cannot connect to Postgres:[/red] {e}")
            db_size = "unavailable"
            market_counts = []

        # Infrastructure stats panel
        redis_info = await _get_redis_info(redis)
        tracked = await _get_tracked_market_count(redis)

        stats_table = Table(show_header=False, show_edge=False, pad_edge=True)
        stats_table.add_column("Label", style="bold", width=24)
        stats_table.add_column("Value")
        stats_table.add_row("Database size", db_size)
        stats_table.add_row("Redis memory", redis_info["used_memory_human"])
        stats_table.add_row("Redis peak memory", redis_info["used_memory_peak_human"])
        stats_table.add_row("Redis clients", str(redis_info["connected_clients"]))
        stats_table.add_row("Tracked markets (Redis)", str(tracked))

        for mc in market_counts:
            stats_table.add_row(f"Markets ({mc['status']})", str(mc["count"]))

        console.print(Panel(stats_table, title="Infrastructure", expand=False))

    finally:
        await close_redis()
        await close_pool()


def status() -> None:
    """System health dashboard: components, data freshness, infrastructure stats."""
    asyncio.run(_status_async())
