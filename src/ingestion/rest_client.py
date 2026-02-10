"""Async REST API client for Kalshi with authentication and rate limiting."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.ingestion.ws_auth import KalshiWSAuth

logger = structlog.get_logger(__name__)


class KalshiRESTClient:
    """Authenticated async HTTP client for the Kalshi REST API."""

    def __init__(self, auth: KalshiWSAuth, base_url: str) -> None:
        self._auth = auth
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=30.0,
        )
        self._rate_limit_remaining: int | None = None
        self._rate_limit_reset: float | None = None

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        """Make an authenticated request with rate limit handling."""
        # Respect rate limits
        if self._rate_limit_remaining is not None and self._rate_limit_remaining <= 1:
            if self._rate_limit_reset:
                wait = max(0, self._rate_limit_reset - asyncio.get_event_loop().time())
                if wait > 0:
                    logger.warning("rate_limit_wait", wait_seconds=wait)
                    await asyncio.sleep(wait)

        headers = self._auth.sign_rest_request(method, urlparse(path).path or path)
        response = await self._client.request(method, path, headers=headers, **kwargs)

        # Track rate limit headers
        if "X-RateLimit-Remaining" in response.headers:
            self._rate_limit_remaining = int(response.headers["X-RateLimit-Remaining"])
        if "X-RateLimit-Reset" in response.headers:
            self._rate_limit_reset = float(response.headers["X-RateLimit-Reset"])

        response.raise_for_status()
        return response.json()

    async def get(self, path: str, params: dict | None = None) -> dict:
        return await self._request("GET", path, params=params)

    async def get_markets(
        self,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 200,
    ) -> dict:
        """GET /trade-api/v2/markets with pagination."""
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        if cursor:
            params["cursor"] = cursor
        return await self.get("/trade-api/v2/markets", params=params)

    async def get_market(self, ticker: str) -> dict:
        """GET /trade-api/v2/markets/{ticker}"""
        return await self.get(f"/trade-api/v2/markets/{ticker}")

    async def get_trades(
        self,
        ticker: str,
        cursor: str | None = None,
        limit: int = 200,
        min_ts: int | None = None,
        max_ts: int | None = None,
    ) -> dict:
        """GET /trade-api/v2/markets/{ticker}/trades"""
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if min_ts:
            params["min_ts"] = min_ts
        if max_ts:
            params["max_ts"] = max_ts
        return await self.get(f"/trade-api/v2/markets/{ticker}/trades", params=params)

    async def get_events(self, cursor: str | None = None, limit: int = 200) -> dict:
        """GET /trade-api/v2/events"""
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self.get("/trade-api/v2/events", params=params)

    async def get_series(self, ticker: str) -> dict:
        """GET /trade-api/v2/series/{ticker}"""
        return await self.get(f"/trade-api/v2/series/{ticker}")

    async def get_candlesticks(
        self,
        series_ticker: str,
        ticker: str,
        period_interval: int = 60,  # minutes
    ) -> dict:
        """GET /trade-api/v2/series/{series_ticker}/markets/{ticker}/candlesticks"""
        params = {"period_interval": period_interval}
        return await self.get(
            f"/trade-api/v2/series/{series_ticker}/markets/{ticker}/candlesticks",
            params=params,
        )
