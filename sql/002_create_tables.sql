-- Raw trade tape
CREATE TABLE IF NOT EXISTS trades (
    ts              TIMESTAMPTZ NOT NULL,
    trade_id        TEXT NOT NULL,
    market_ticker   TEXT NOT NULL,
    yes_price       SMALLINT NOT NULL,
    no_price        SMALLINT NOT NULL,
    count           NUMERIC(12,2) NOT NULL,
    taker_side      TEXT NOT NULL,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ticker v2 updates (incremental)
CREATE TABLE IF NOT EXISTS ticker_updates (
    ts                          TIMESTAMPTZ NOT NULL,
    market_ticker               TEXT NOT NULL,
    price                       SMALLINT,
    volume_delta                NUMERIC(12,2),
    open_interest_delta         NUMERIC(12,2),
    dollar_volume_delta         INTEGER,
    dollar_open_interest_delta  INTEGER,
    received_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Orderbook snapshots (periodic full snapshots)
CREATE TABLE IF NOT EXISTS orderbook_snapshots (
    ts              TIMESTAMPTZ NOT NULL,
    market_ticker   TEXT NOT NULL,
    yes_levels      JSONB NOT NULL,
    no_levels       JSONB NOT NULL,
    spread          SMALLINT,
    yes_depth_5     INTEGER,
    no_depth_5      INTEGER,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Orderbook deltas (raw, every change)
CREATE TABLE IF NOT EXISTS orderbook_deltas (
    ts              TIMESTAMPTZ NOT NULL,
    market_ticker   TEXT NOT NULL,
    price           SMALLINT NOT NULL,
    delta           NUMERIC(12,2) NOT NULL,
    side            TEXT NOT NULL,
    is_own_order    BOOLEAN NOT NULL DEFAULT FALSE,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Market metadata (upserted from REST discovery)
CREATE TABLE IF NOT EXISTS markets (
    ticker          TEXT PRIMARY KEY,
    event_ticker    TEXT NOT NULL,
    series_ticker   TEXT NOT NULL,
    title           TEXT NOT NULL,
    subtitle        TEXT,
    status          TEXT NOT NULL,
    market_type     TEXT,
    close_time      TIMESTAMPTZ,
    result          TEXT,
    last_synced_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Series metadata
CREATE TABLE IF NOT EXISTS series (
    ticker          TEXT PRIMARY KEY,
    title           TEXT,
    category        TEXT,
    tags            TEXT[],
    last_synced_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Events metadata
CREATE TABLE IF NOT EXISTS events (
    ticker          TEXT PRIMARY KEY,
    series_ticker   TEXT NOT NULL,
    title           TEXT,
    status          TEXT,
    market_count    INTEGER,
    last_synced_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Market lifecycle events
CREATE TABLE IF NOT EXISTS lifecycle_events (
    ts              TIMESTAMPTZ NOT NULL,
    market_ticker   TEXT NOT NULL,
    market_id       TEXT,
    status          TEXT NOT NULL,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- System health log
CREATE TABLE IF NOT EXISTS system_health (
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    component       TEXT NOT NULL,
    status          TEXT NOT NULL,
    details         JSONB,
    message_rate    REAL,
    lag_ms          REAL
);
