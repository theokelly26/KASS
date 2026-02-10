"""Kalshi WebSocket connection manager — the core ingestion component.

Manages a persistent WebSocket connection with authentication, subscription
management, automatic reconnection, message parsing, and Redis stream publishing.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import orjson
import websockets
import websockets.asyncio.client
import structlog

from src.config import AppConfig, get_config
from src.cache.redis_client import get_redis
from src.cache.state import OrderbookStateManager
from src.cache.streams import RedisStreamPublisher
from src.ingestion.ws_auth import KalshiWSAuth
from src.ingestion.ws_router import MESSAGE_HANDLERS
from src.models import (
    KalshiTrade,
    KalshiTickerV2,
    OrderbookDelta,
    OrderbookSnapshot,
    MarketLifecycleEvent,
    EventLifecycleEvent,
)

logger = structlog.get_logger(__name__)


@dataclass
class SubscriptionInfo:
    """Tracks a single WebSocket subscription."""

    sid: int
    channels: list[str]
    market_tickers: list[str] | None = None
    last_seq: int = 0


class KalshiWSManager:
    """
    Manages a persistent WebSocket connection to Kalshi.

    Handles authentication, subscription management, reconnection,
    message parsing, and publishing to Redis streams.
    """

    def __init__(
        self,
        auth: KalshiWSAuth,
        publisher: RedisStreamPublisher,
        state_mgr: OrderbookStateManager,
        config: AppConfig,
    ) -> None:
        self._auth = auth
        self._publisher = publisher
        self._state_mgr = state_mgr
        self._config = config

        self._ws: websockets.asyncio.client.ClientConnection | None = None
        self._connected = False
        self._reconnect_delay = 1.0
        self._next_sid = 1

        self.subscriptions: dict[int, SubscriptionInfo] = {}
        self.sequence_numbers: dict[int, int] = {}

        # Stats
        self._msg_counts: dict[str, int] = {}
        self._connect_time: float = 0
        self._last_stats_time: float = 0

    # ── Connection lifecycle ──────────────────────────────────────────

    async def connect(self) -> None:
        """Establish authenticated WebSocket connection with retry logic."""
        while True:
            try:
                headers = self._auth.create_headers()
                self._ws = await websockets.asyncio.client.connect(
                    self._config.kalshi.ws_url,
                    additional_headers=headers,
                    ping_interval=self._config.tuning.ws_ping_interval,
                    ping_timeout=self._config.tuning.ws_pong_timeout,
                    max_size=10 * 1024 * 1024,  # 10MB max message
                )
                self._connected = True
                self._connect_time = time.time()
                self._reconnect_delay = 1.0  # Reset backoff
                logger.info("websocket_connected", url=self._config.kalshi.ws_url)

                # Re-subscribe to all previous subscriptions on reconnect
                await self._resubscribe_all()

                # Enter the message loop
                await self._message_loop()

            except websockets.ConnectionClosed as e:
                logger.warning("websocket_disconnected", code=e.code, reason=e.reason)
            except websockets.InvalidHandshake as e:
                logger.error("websocket_auth_failed", error=str(e))
            except OSError as e:
                logger.error("websocket_connection_error", error=str(e))
            except Exception:
                logger.exception("websocket_unexpected_error")
            finally:
                self._connected = False
                self._ws = None

            # Exponential backoff
            logger.info("websocket_reconnecting", delay=self._reconnect_delay)
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(
                self._reconnect_delay * 2,
                self._config.tuning.ws_reconnect_max_delay,
            )

    async def _resubscribe_all(self) -> None:
        """Re-subscribe to all previous subscriptions after reconnect."""
        if not self.subscriptions:
            return

        logger.info("resubscribing", count=len(self.subscriptions))
        for sub in list(self.subscriptions.values()):
            try:
                await self._send_subscribe(sub.channels, sub.market_tickers)
            except Exception:
                logger.exception("resubscribe_failed", sid=sub.sid)

    # ── Subscription management ───────────────────────────────────────

    async def subscribe(
        self,
        channels: list[str],
        market_tickers: list[str] | None = None,
    ) -> int:
        """Subscribe to channels. Returns subscription ID."""
        sid = self._next_sid
        self._next_sid += 1

        self.subscriptions[sid] = SubscriptionInfo(
            sid=sid,
            channels=channels,
            market_tickers=market_tickers,
        )

        if self._connected:
            await self._send_subscribe(channels, market_tickers)

        logger.info(
            "subscription_added",
            sid=sid,
            channels=channels,
            tickers_count=len(market_tickers) if market_tickers else "all",
        )
        return sid

    async def _send_subscribe(
        self,
        channels: list[str],
        market_tickers: list[str] | None = None,
    ) -> None:
        """Send subscribe command over the WebSocket."""
        if not self._ws:
            return

        cmd: dict[str, Any] = {
            "id": self._next_sid,
            "cmd": "subscribe",
            "params": {"channels": channels},
        }
        if market_tickers:
            cmd["params"]["market_tickers"] = market_tickers

        await self._ws.send(orjson.dumps(cmd).decode())

    async def update_subscription(
        self,
        sid: int,
        add_tickers: list[str] | None = None,
        remove_tickers: list[str] | None = None,
    ) -> None:
        """Add or remove market tickers from an existing subscription."""
        sub = self.subscriptions.get(sid)
        if not sub:
            logger.warning("update_unknown_subscription", sid=sid)
            return

        if not self._ws:
            return

        if add_tickers:
            cmd = {
                "id": sid,
                "cmd": "update_subscription",
                "params": {
                    "sids": [sid],
                    "market_tickers": add_tickers,
                    "action": "add_markets",
                },
            }
            await self._ws.send(orjson.dumps(cmd).decode())
            if sub.market_tickers is not None:
                sub.market_tickers.extend(add_tickers)

        if remove_tickers:
            cmd = {
                "id": sid,
                "cmd": "update_subscription",
                "params": {
                    "sids": [sid],
                    "market_tickers": remove_tickers,
                    "action": "remove_markets",
                },
            }
            await self._ws.send(orjson.dumps(cmd).decode())
            if sub.market_tickers is not None:
                sub.market_tickers = [
                    t for t in sub.market_tickers if t not in remove_tickers
                ]

    async def unsubscribe(self, sids: list[int]) -> None:
        """Unsubscribe from one or more subscriptions."""
        if self._ws:
            cmd = {
                "id": self._next_sid,
                "cmd": "unsubscribe",
                "params": {"sids": sids},
            }
            await self._ws.send(orjson.dumps(cmd).decode())

        for sid in sids:
            self.subscriptions.pop(sid, None)
            self.sequence_numbers.pop(sid, None)

        logger.info("unsubscribed", sids=sids)

    # ── Message processing ────────────────────────────────────────────

    async def _message_loop(self) -> None:
        """Main message processing loop."""
        self._last_stats_time = time.time()

        async for raw in self._ws:
            try:
                msg = orjson.loads(raw)
            except orjson.JSONDecodeError:
                logger.error("invalid_json", raw=raw[:200] if isinstance(raw, str) else str(raw)[:200])
                continue

            msg_type = msg.get("type")
            if not msg_type:
                # Could be a command response
                if "id" in msg:
                    await self._handle_command_response(msg)
                continue

            # Track sequence numbers
            sid = msg.get("sid")
            seq = msg.get("seq")
            if sid is not None and seq is not None:
                if await self._detect_sequence_gap(sid, seq):
                    logger.warning(
                        "sequence_gap_detected",
                        sid=sid,
                        expected=self.sequence_numbers.get(sid, 0) + 1,
                        received=seq,
                    )
                self.sequence_numbers[sid] = seq

            # Route to handler
            handler_name = MESSAGE_HANDLERS.get(msg_type)
            if handler_name:
                handler = getattr(self, handler_name, None)
                if handler:
                    try:
                        await handler(msg)
                    except Exception:
                        logger.exception("handler_error", msg_type=msg_type)
            else:
                logger.debug("unknown_message_type", msg_type=msg_type)

            # Track stats
            self._msg_counts[msg_type] = self._msg_counts.get(msg_type, 0) + 1

            # Log stats every 60 seconds
            now = time.time()
            if now - self._last_stats_time >= 60:
                await self._log_stats()
                self._last_stats_time = now

    async def _detect_sequence_gap(self, sid: int, seq: int) -> bool:
        """Detect if we missed messages based on sequence numbers."""
        last_seq = self.sequence_numbers.get(sid)
        if last_seq is None:
            return False
        return seq > last_seq + 1

    async def _log_stats(self) -> None:
        """Log message rate statistics."""
        uptime = time.time() - self._connect_time if self._connect_time else 0
        total = sum(self._msg_counts.values())
        pub_counts = self._publisher.get_counts()

        logger.info(
            "ws_stats",
            uptime_seconds=int(uptime),
            total_messages=total,
            by_type=dict(self._msg_counts),
            published=pub_counts,
            subscriptions=len(self.subscriptions),
        )
        self._msg_counts.clear()

    # ── Message handlers ──────────────────────────────────────────────

    async def _handle_trade(self, msg: dict) -> None:
        """Parse trade message, validate, publish to Redis."""
        msg_data = msg.get("msg", {})
        try:
            trade = KalshiTrade.model_validate(msg_data)
            await self._publisher.publish_trade(trade)
        except Exception:
            logger.exception("trade_parse_error", msg=msg_data)

    async def _handle_ticker_v2(self, msg: dict) -> None:
        """Parse ticker update, validate, publish to Redis."""
        msg_data = msg.get("msg", {})
        try:
            ticker = KalshiTickerV2.model_validate(msg_data)
            await self._publisher.publish_ticker(ticker)
        except Exception:
            logger.exception("ticker_parse_error", msg=msg_data)

    async def _handle_orderbook_snapshot(self, msg: dict) -> None:
        """Parse full orderbook snapshot, update state, publish to Redis."""
        msg_data = msg.get("msg", {})
        try:
            snapshot = OrderbookSnapshot.model_validate(msg_data)
            await self._state_mgr.apply_snapshot(snapshot)
            await self._publisher.publish_orderbook_snapshot(snapshot)
        except Exception:
            logger.exception("ob_snapshot_parse_error", msg=msg_data)

    async def _handle_orderbook_delta(self, msg: dict) -> None:
        """Parse orderbook delta, update state, publish to Redis."""
        msg_data = msg.get("msg", {})
        try:
            delta = OrderbookDelta.model_validate(msg_data)
            await self._state_mgr.apply_delta(delta)
            await self._publisher.publish_orderbook_delta(delta)
        except Exception:
            logger.exception("ob_delta_parse_error", msg=msg_data)

    async def _handle_lifecycle(self, msg: dict) -> None:
        """Parse market lifecycle event, publish to Redis."""
        msg_data = msg.get("msg", {})
        try:
            event = MarketLifecycleEvent.model_validate(msg_data)
            await self._publisher.publish_lifecycle(event)
        except Exception:
            logger.exception("lifecycle_parse_error", msg=msg_data)

    async def _handle_event_lifecycle(self, msg: dict) -> None:
        """Parse event-level lifecycle message, publish to Redis."""
        msg_data = msg.get("msg", {})
        try:
            event = EventLifecycleEvent.model_validate(msg_data)
            await self._publisher.publish_event_lifecycle(event)
        except Exception:
            logger.exception("event_lifecycle_parse_error", msg=msg_data)

    async def _handle_subscribed(self, msg: dict) -> None:
        """Handle subscription confirmation."""
        sid = msg.get("id")
        logger.info("subscription_confirmed", sid=sid, msg=msg)

    async def _handle_unsubscribed(self, msg: dict) -> None:
        """Handle unsubscription confirmation."""
        sid = msg.get("id")
        logger.info("unsubscription_confirmed", sid=sid)

    async def _handle_error(self, msg: dict) -> None:
        """Handle error messages from the server."""
        logger.error("ws_server_error", msg=msg)

    async def _handle_ok(self, msg: dict) -> None:
        """Handle OK responses."""
        logger.debug("ws_ok", msg=msg)

    async def _handle_command_response(self, msg: dict) -> None:
        """Handle command responses (subscribe/unsubscribe confirmations)."""
        logger.debug("ws_command_response", msg=msg)


async def main() -> None:
    """Entry point for the WebSocket manager process."""
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
    auth = KalshiWSAuth(
        key_id=config.kalshi.api_key_id,
        private_key_path=str(config.kalshi.private_key_path),
    )
    redis = await get_redis(config.redis)
    publisher = RedisStreamPublisher(redis)
    state_mgr = OrderbookStateManager(redis)

    manager = KalshiWSManager(auth, publisher, state_mgr, config)

    # Subscribe to all broadcast channels
    await manager.subscribe(["ticker_v2"])
    await manager.subscribe(["trade"])
    await manager.subscribe(["market_lifecycle_v2"])

    # Connect and run forever
    await manager.connect()


if __name__ == "__main__":
    asyncio.run(main())
