# KASS — Kalshi Alpha Signal System

## Project Overview
Phase 1 data infrastructure for capturing all Kalshi market data into TimescaleDB via Redis streams.

## Tech Stack
- **Python 3.11+** with asyncio for all I/O
- **Pydantic v2** for data validation
- **TimescaleDB** (PostgreSQL extension) for time-series storage
- **Redis** streams for message passing, caching for orderbook state
- **websockets** library for Kalshi WebSocket connections
- **psycopg[pool]** (psycopg3) for async Postgres
- **redis.asyncio** for async Redis
- **httpx** for async REST API calls
- **structlog** for structured JSON logging
- **cryptography** for RSA-PSS authentication

## Architecture
```
Kalshi WSS → Redis Streams → TimescaleDB
                ↑
        Market Discovery (REST poller)
```

## Key Conventions
- All config via environment variables (see .env.example)
- Pydantic models in src/models/ are the shared contract between all components
- Redis stream names: kalshi:trades, kalshi:ticker_v2, kalshi:orderbook:deltas, kalshi:orderbook:snapshots, kalshi:lifecycle, kalshi:system
- All database writers use consumer groups with XREADGROUP for reliable consumption
- Type hints everywhere, no blocking calls

## Running
```bash
# Setup
pip install -e ".[dev]"
bash scripts/setup_db.sh

# Run all services
pm2 start processes/ecosystem.config.js

# Run tests
pytest tests/
```

## File Layout
- `src/config.py` — Central config from env vars
- `src/models/` — Pydantic models (trade, ticker, orderbook, market, lifecycle)
- `src/ingestion/` — WebSocket client, auth, message routing
- `src/discovery/` — Market scanner, series mapper, subscription manager
- `src/persistence/` — DB connection pool, writers, gap detection, backfill
- `src/cache/` — Redis client, stream pub/sub, orderbook state
- `src/monitoring/` — Health checks, Telegram alerts
