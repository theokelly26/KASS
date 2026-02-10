# KASS — Kalshi Alpha Signal System

## Project Overview
Phase 1: Data infrastructure capturing all Kalshi market data into TimescaleDB via Redis streams.
Phase 2: Signal generation layer — 5 real-time signal processors + aggregator producing composite alpha scores.
Phase 2.5: Observability & analysis layer — signal logging, price snapshots, Grafana dashboards, CLI tool, analysis SQL library.

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
- **typer** + **rich** for CLI monitoring tool
- **Grafana** for dashboards (localhost:3000)

## Architecture
```
Phase 1:  Kalshi WSS → Redis Streams → TimescaleDB
                            ↑
                    Market Discovery (REST poller)

Phase 2:  Redis Streams → Signal Processors → kalshi:signals:all → Aggregator → kalshi:signals:composite

Phase 2.5: kalshi:signals:all → SignalWriter → signal_log, composite_log, regime_log (TimescaleDB)
            PriceSnapshotService → price_snapshots (every 30s)
            ViewRefresher → REFRESH MATERIALIZED VIEW signal_outcomes (every 15m)
            Grafana (localhost:3000) → 4 dashboards
            CLI (kass) → status, signals, markets, market, query, tail
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

# Run all services (16 processes)
pm2 start processes/ecosystem.config.js

# Run tests
pytest tests/

# CLI commands
kass status                    # System health dashboard
kass signals --live            # Live signal feed from Redis
kass signals --limit 20        # Recent signals from DB
kass markets --sort volume     # Market activity overview
kass market <TICKER>           # Deep dive on one market
kass query signal_quality      # Run named analysis SQL query
kass tail trades               # Tail a Redis stream

# Grafana setup
bash scripts/setup_grafana.sh  # Install, start, provision dashboards
# Then open http://localhost:3000 (admin/admin)
```

## File Layout
- `src/config.py` — Central config from env vars
- `src/models/` — Pydantic models (trade, ticker, orderbook, market, lifecycle)
- `src/ingestion/` — WebSocket client, auth, message routing
- `src/discovery/` — Market scanner, series mapper, subscription manager
- `src/persistence/` — DB connection pool, writers, gap detection, backfill
- `src/cache/` — Redis client, stream pub/sub, orderbook state
- `src/monitoring/` — Health checks, Telegram alerts, price snapshots, view refresher
- `src/signals/` — Phase 2 signal generation layer:
  - `models.py` — Signal, CompositeSignal, MarketRegime, SignalDirection enums
  - `base.py` — BaseSignalProcessor abstract class (all processors inherit)
  - `streams.py` — SignalPublisher for signal-specific Redis streams
  - `config.py` — Configuration for all signal processors
  - `flow/toxicity.py` — VPIN-based flow toxicity classifier
  - `flow/oi_divergence.py` — OI vs price divergence detector (4 regimes)
  - `microstructure/regime.py` — Market regime classifier (DEAD/QUIET/ACTIVE/INFORMED/PRE_SETTLE)
  - `cross_market/propagation.py` — Cross-market repricing opportunity detector
  - `cross_market/lifecycle_alpha.py` — Settlement cascade and new market scanner
  - `aggregator/aggregator.py` — Weighted signal combiner with regime modifiers
- `src/cli/` — CLI monitoring tool (typer + rich):
  - `main.py` — Entry point, registers all commands
  - `display.py` — Rich formatting helpers
  - `commands/status.py` — System health dashboard
  - `commands/signals.py` — Live/recent signal feed
  - `commands/markets.py` — Market activity overview
  - `commands/market.py` — Single market deep dive
  - `commands/query.py` — Run named analysis SQL queries
  - `commands/tail.py` — Tail Redis streams in real time
- `analysis/queries/` — SQL query library (01-05)
- `grafana/dashboards/` — 4 Grafana dashboard JSONs
- `scripts/setup_grafana.sh` — Grafana install and provisioning
- `scripts/provision_grafana.py` — API-based datasource and dashboard provisioning

## Phase 2.5 Tables
- `signal_log` — Every signal from every processor (hypertable)
- `composite_log` — Every composite from aggregator (hypertable)
- `regime_log` — Every regime change detected (hypertable)
- `price_snapshots` — Periodic price captures every 30s (hypertable)
- `signal_outcomes` — Materialized view joining signals to subsequent price moves

## Phase 2 Signal Streams
- `kalshi:signals:flow_toxicity` — VPIN and burst signals
- `kalshi:signals:oi_divergence` — OI/price divergence signals
- `kalshi:signals:regime` — Market regime change signals
- `kalshi:signals:cross_market` — Cross-market propagation signals
- `kalshi:signals:lifecycle` — Settlement cascade and new market signals
- `kalshi:signals:all` — All signals (duplicate for aggregator)
- `kalshi:signals:composite` — Final composite signals (for Phase 3 execution)
