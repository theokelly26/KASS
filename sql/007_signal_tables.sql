-- Signal log: every signal emitted by every processor
CREATE TABLE IF NOT EXISTS signal_log (
    ts                  TIMESTAMPTZ NOT NULL,
    signal_id           TEXT NOT NULL,
    signal_type         TEXT NOT NULL,
    market_ticker       TEXT NOT NULL,
    event_ticker        TEXT,
    series_ticker       TEXT,
    direction           TEXT NOT NULL,
    strength            REAL NOT NULL,
    confidence          REAL NOT NULL,
    urgency             TEXT NOT NULL,
    metadata            JSONB,
    ttl_seconds         INTEGER NOT NULL,
    expired_at          TIMESTAMPTZ,
    received_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
SELECT create_hypertable('signal_log', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_signal_type ON signal_log (signal_type, ts DESC);
CREATE INDEX IF NOT EXISTS idx_signal_market ON signal_log (market_ticker, ts DESC);
CREATE INDEX IF NOT EXISTS idx_signal_direction ON signal_log (direction, ts DESC);
CREATE INDEX IF NOT EXISTS idx_signal_strength ON signal_log (strength DESC, ts DESC);

-- Composite signal log: every composite the aggregator published
CREATE TABLE IF NOT EXISTS composite_log (
    ts                  TIMESTAMPTZ NOT NULL,
    market_ticker       TEXT NOT NULL,
    event_ticker        TEXT,
    series_ticker       TEXT,
    direction           TEXT NOT NULL,
    composite_score     REAL NOT NULL,
    regime              TEXT NOT NULL,
    active_signal_count INTEGER NOT NULL,
    active_signal_ids   TEXT[],
    received_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
SELECT create_hypertable('composite_log', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_composite_market ON composite_log (market_ticker, ts DESC);
CREATE INDEX IF NOT EXISTS idx_composite_score ON composite_log (composite_score DESC, ts DESC);
CREATE INDEX IF NOT EXISTS idx_composite_regime ON composite_log (regime, ts DESC);

-- Regime log: every regime change detected
CREATE TABLE IF NOT EXISTS regime_log (
    ts                  TIMESTAMPTZ NOT NULL,
    market_ticker       TEXT NOT NULL,
    old_regime          TEXT,
    new_regime          TEXT NOT NULL,
    trade_rate          REAL,
    message_rate        REAL,
    depth_imbalance     REAL,
    received_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
SELECT create_hypertable('regime_log', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_regime_market ON regime_log (market_ticker, ts DESC);

-- Price snapshots: periodic price captures for signal validation
CREATE TABLE IF NOT EXISTS price_snapshots (
    ts                  TIMESTAMPTZ NOT NULL,
    market_ticker       TEXT NOT NULL,
    yes_price           SMALLINT,
    yes_bid             SMALLINT,
    yes_ask             SMALLINT,
    spread              SMALLINT,
    volume_24h          INTEGER,
    open_interest       INTEGER,
    received_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
SELECT create_hypertable('price_snapshots', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_price_snap_market ON price_snapshots (market_ticker, ts DESC);

-- Unique index on signal_outcomes for CONCURRENTLY refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_signal_log_id ON signal_log (signal_id, ts);

-- Signal outcome tracking: join signals to subsequent price moves
CREATE MATERIALIZED VIEW IF NOT EXISTS signal_outcomes AS
SELECT
    s.signal_id,
    s.signal_type,
    s.market_ticker,
    s.direction,
    s.strength,
    s.confidence,
    s.metadata,
    s.ts as signal_ts,
    p_at.yes_price as price_at_signal,
    p_1m.yes_price as price_1m_after,
    p_5m.yes_price as price_5m_after,
    p_15m.yes_price as price_15m_after,
    p_60m.yes_price as price_60m_after,
    CASE
        WHEN s.direction = 'buy_yes' AND p_5m.yes_price > p_at.yes_price THEN TRUE
        WHEN s.direction = 'buy_no' AND p_5m.yes_price < p_at.yes_price THEN TRUE
        WHEN s.direction = 'neutral' THEN NULL
        ELSE FALSE
    END as correct_5m,
    CASE
        WHEN s.direction = 'buy_yes' AND p_15m.yes_price > p_at.yes_price THEN TRUE
        WHEN s.direction = 'buy_no' AND p_15m.yes_price < p_at.yes_price THEN TRUE
        WHEN s.direction = 'neutral' THEN NULL
        ELSE FALSE
    END as correct_15m,
    COALESCE(p_5m.yes_price - p_at.yes_price, 0) as move_5m,
    COALESCE(p_15m.yes_price - p_at.yes_price, 0) as move_15m,
    COALESCE(p_60m.yes_price - p_at.yes_price, 0) as move_60m
FROM signal_log s
LEFT JOIN LATERAL (
    SELECT yes_price FROM price_snapshots p
    WHERE p.market_ticker = s.market_ticker
    AND p.ts >= s.ts - interval '30 seconds'
    AND p.ts <= s.ts + interval '30 seconds'
    ORDER BY ABS(EXTRACT(EPOCH FROM p.ts - s.ts))
    LIMIT 1
) p_at ON TRUE
LEFT JOIN LATERAL (
    SELECT yes_price FROM price_snapshots p
    WHERE p.market_ticker = s.market_ticker
    AND p.ts >= s.ts + interval '50 seconds'
    AND p.ts <= s.ts + interval '70 seconds'
    ORDER BY p.ts
    LIMIT 1
) p_1m ON TRUE
LEFT JOIN LATERAL (
    SELECT yes_price FROM price_snapshots p
    WHERE p.market_ticker = s.market_ticker
    AND p.ts >= s.ts + interval '4 minutes 30 seconds'
    AND p.ts <= s.ts + interval '5 minutes 30 seconds'
    ORDER BY p.ts
    LIMIT 1
) p_5m ON TRUE
LEFT JOIN LATERAL (
    SELECT yes_price FROM price_snapshots p
    WHERE p.market_ticker = s.market_ticker
    AND p.ts >= s.ts + interval '14 minutes'
    AND p.ts <= s.ts + interval '16 minutes'
    ORDER BY p.ts
    LIMIT 1
) p_15m ON TRUE
LEFT JOIN LATERAL (
    SELECT yes_price FROM price_snapshots p
    WHERE p.market_ticker = s.market_ticker
    AND p.ts >= s.ts + interval '55 minutes'
    AND p.ts <= s.ts + interval '65 minutes'
    ORDER BY p.ts
    LIMIT 1
) p_60m ON TRUE
WHERE s.direction != 'neutral';

CREATE UNIQUE INDEX IF NOT EXISTS idx_signal_outcomes_id ON signal_outcomes (signal_id);
