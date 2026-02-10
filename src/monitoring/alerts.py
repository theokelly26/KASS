"""Alert dispatcher with Telegram integration and cooldown logic."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx
import structlog

from src.config import MonitoringConfig

logger = structlog.get_logger(__name__)


class AlertDispatcher:
    """
    Sends alerts via configured channels.
    Uses Telegram Bot API for push notifications.
    Implements cooldown to prevent alert storms.
    """

    def __init__(self, config: MonitoringConfig) -> None:
        self._config = config
        self._last_alert: dict[str, float] = {}  # component -> last alert timestamp
        self._client = httpx.AsyncClient(timeout=10.0)

    async def send_alert(
        self, severity: str, component: str, message: str
    ) -> None:
        """
        Send an alert if cooldown has expired for this component.

        Args:
            severity: "critical" | "warning" | "info"
            component: The system component that triggered the alert
            message: Human-readable alert message
        """
        # Check cooldown
        now = time.time()
        last = self._last_alert.get(component, 0)
        if now - last < self._config.alert_cooldown:
            logger.debug(
                "alert_cooldown",
                component=component,
                remaining=int(self._config.alert_cooldown - (now - last)),
            )
            return

        self._last_alert[component] = now

        # Send via Telegram
        if self._config.telegram_bot_token and self._config.telegram_chat_id:
            await self._send_telegram(severity, component, message)
        else:
            logger.warning("no_alert_channel_configured", severity=severity, message=message)

    async def _send_telegram(
        self, severity: str, component: str, message: str
    ) -> None:
        """Send alert via Telegram Bot API."""
        emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(severity, "⚪")

        text = (
            f"{emoji} *KASS Alert — {severity.upper()}*\n"
            f"Component: `{component}`\n"
            f"Time: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"\n{message}"
        )

        url = f"https://api.telegram.org/bot{self._config.telegram_bot_token}/sendMessage"

        try:
            response = await self._client.post(
                url,
                json={
                    "chat_id": self._config.telegram_chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
            )
            if response.status_code != 200:
                logger.error(
                    "telegram_send_failed",
                    status=response.status_code,
                    body=response.text,
                )
            else:
                logger.info("alert_sent", severity=severity, component=component)
        except Exception:
            logger.exception("telegram_send_error")

    async def send_daily_summary(self) -> None:
        """
        Daily digest with system statistics.
        Should be called once per day (e.g., via cron or asyncio scheduler).
        """
        from src.config import get_config
        from src.persistence.db import get_connection

        config = get_config()

        try:
            async with get_connection(config.postgres) as conn:
                async with conn.cursor() as cur:
                    # Trade count today
                    await cur.execute(
                        "SELECT COUNT(*) FROM trades WHERE ts > NOW() - INTERVAL '24 hours'"
                    )
                    trade_count = (await cur.fetchone())[0]

                    # Active markets
                    await cur.execute(
                        "SELECT COUNT(*) FROM markets WHERE status = 'open'"
                    )
                    market_count = (await cur.fetchone())[0]

                    # Health status
                    await cur.execute(
                        """
                        SELECT component, status FROM system_health
                        WHERE ts > NOW() - INTERVAL '5 minutes'
                        ORDER BY ts DESC
                        """
                    )
                    health = await cur.fetchall()

            summary = (
                f"📊 *KASS Daily Summary*\n"
                f"\n"
                f"Trades ingested (24h): {trade_count:,}\n"
                f"Active markets: {market_count}\n"
                f"Health: {len([h for h in health if h[1] == 'ok'])}/{len(health)} OK\n"
            )

            if self._config.telegram_bot_token and self._config.telegram_chat_id:
                url = f"https://api.telegram.org/bot{self._config.telegram_bot_token}/sendMessage"
                await self._client.post(
                    url,
                    json={
                        "chat_id": self._config.telegram_chat_id,
                        "text": summary,
                        "parse_mode": "Markdown",
                    },
                )
                logger.info("daily_summary_sent")
        except Exception:
            logger.exception("daily_summary_error")
