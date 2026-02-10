"""Health monitoring for all KASS system components.

Checks health of all components every 30 seconds, writes to system_health
table, and sends alerts on failures.
"""

from __future__ import annotations

import asyncio
import shutil
import time
from datetime import datetime, timezone
from typing import Any

import orjson
import redis.asyncio as aioredis
import structlog

from src.cache.redis_client import get_redis
from src.cache.state import KEY_HEALTH
from src.cache.streams import (
    STREAM_TRADES,
    STREAM_TICKER_V2,
    STREAM_ORDERBOOK_DELTAS,
    STREAM_LIFECYCLE,
)
from src.config import AppConfig, get_config
from src.monitoring.alerts import AlertDispatcher
from src.persistence.db import get_connection, get_pool

logger = structlog.get_logger(__name__)


class HealthMonitor:
    """
    Checks health of all system components every N seconds.
    Writes to system_health table and sends alerts on failures.
    """

    CHECKS = [
        "redis_responsive",
        "postgres_responsive",
        "trade_stream_backlog",
        "ticker_stream_backlog",
        "orderbook_stream_backlog",
        "lifecycle_stream_backlog",
        "message_rate",
        "disk_usage",
    ]

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._alerter = AlertDispatcher(config.monitoring)
        self._last_stream_lengths: dict[str, int] = {}

    async def run(self) -> None:
        """Main health check loop."""
        interval = self._config.monitoring.health_check_interval
        logger.info("health_monitor_started", interval=interval)

        while True:
            try:
                results = await self._run_all_checks()
                await self._write_results(results)
                await self._update_redis_health(results)
                await self._check_alerts(results)
            except Exception:
                logger.exception("health_check_error")

            await asyncio.sleep(interval)

    async def _run_all_checks(self) -> list[dict[str, Any]]:
        """Run all health checks and return results."""
        results = []

        # Redis check
        results.append(await self._check_redis())

        # Postgres check
        results.append(await self._check_postgres())

        # Stream backlogs
        for stream, name in [
            (STREAM_TRADES, "trade_stream_backlog"),
            (STREAM_TICKER_V2, "ticker_stream_backlog"),
            (STREAM_ORDERBOOK_DELTAS, "orderbook_stream_backlog"),
            (STREAM_LIFECYCLE, "lifecycle_stream_backlog"),
        ]:
            results.append(await self._check_stream_backlog(stream, name))

        # Disk usage
        results.append(self._check_disk_usage())

        return results

    async def _check_redis(self) -> dict[str, Any]:
        """Check Redis connectivity."""
        try:
            redis = await get_redis(self._config.redis)
            start = time.time()
            await redis.ping()
            latency_ms = (time.time() - start) * 1000
            return {
                "component": "redis",
                "status": "ok",
                "details": {"latency_ms": round(latency_ms, 2)},
            }
        except Exception as e:
            return {
                "component": "redis",
                "status": "critical",
                "details": {"error": str(e)},
            }

    async def _check_postgres(self) -> dict[str, Any]:
        """Check Postgres connectivity."""
        try:
            start = time.time()
            async with get_connection(self._config.postgres) as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
            latency_ms = (time.time() - start) * 1000
            return {
                "component": "postgres",
                "status": "ok",
                "details": {"latency_ms": round(latency_ms, 2)},
            }
        except Exception as e:
            return {
                "component": "postgres",
                "status": "critical",
                "details": {"error": str(e)},
            }

    async def _check_stream_backlog(
        self, stream: str, component: str
    ) -> dict[str, Any]:
        """Check Redis stream length (backlog of unprocessed messages)."""
        try:
            redis = await get_redis(self._config.redis)
            length = await redis.xlen(stream)

            prev = self._last_stream_lengths.get(stream, 0)
            rate = (length - prev) / self._config.monitoring.health_check_interval
            self._last_stream_lengths[stream] = length

            status = "ok"
            if length > 10000:
                status = "warning"
            if length > 50000:
                status = "critical"

            return {
                "component": component,
                "status": status,
                "details": {"length": length, "rate_per_sec": round(rate, 2)},
                "message_rate": abs(rate),
            }
        except Exception as e:
            return {
                "component": component,
                "status": "warning",
                "details": {"error": str(e)},
            }

    def _check_disk_usage(self) -> dict[str, Any]:
        """Check disk usage."""
        usage = shutil.disk_usage("/")
        pct = usage.used / usage.total * 100
        status = "ok"
        if pct > 80:
            status = "warning"
        if pct > 90:
            status = "critical"

        return {
            "component": "disk",
            "status": status,
            "details": {
                "used_pct": round(pct, 1),
                "free_gb": round(usage.free / (1024**3), 1),
            },
        }

    async def _write_results(self, results: list[dict[str, Any]]) -> None:
        """Write health check results to the system_health table."""
        try:
            async with get_connection(self._config.postgres) as conn:
                async with conn.cursor() as cur:
                    for r in results:
                        await cur.execute(
                            """
                            INSERT INTO system_health (component, status, details,
                                message_rate, lag_ms)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (
                                r["component"],
                                r["status"],
                                orjson.dumps(r.get("details", {})).decode(),
                                r.get("message_rate"),
                                r.get("details", {}).get("latency_ms"),
                            ),
                        )
                await conn.commit()
        except Exception:
            logger.exception("health_write_error")

    async def _update_redis_health(self, results: list[dict[str, Any]]) -> None:
        """Update Redis health keys for external monitoring."""
        try:
            redis = await get_redis(self._config.redis)
            for r in results:
                key = KEY_HEALTH.format(component=r["component"])
                await redis.set(
                    key,
                    orjson.dumps(r).decode(),
                    ex=60,  # 60 second TTL
                )
        except Exception:
            logger.exception("health_redis_update_error")

    async def _check_alerts(self, results: list[dict[str, Any]]) -> None:
        """Send alerts for critical/warning statuses."""
        for r in results:
            if r["status"] == "critical":
                await self._alerter.send_alert(
                    severity="critical",
                    component=r["component"],
                    message=f"CRITICAL: {r['component']} - {r.get('details', {})}",
                )
            elif r["status"] == "warning":
                await self._alerter.send_alert(
                    severity="warning",
                    component=r["component"],
                    message=f"WARNING: {r['component']} - {r.get('details', {})}",
                )


async def main() -> None:
    """Entry point for the health monitor process."""
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
    monitor = HealthMonitor(config)
    await monitor.run()


if __name__ == "__main__":
    asyncio.run(main())
