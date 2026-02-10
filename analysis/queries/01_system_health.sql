-- =============================================================================
-- KASS Analysis Library: 01 - System Health
-- =============================================================================
-- Purpose: Operational dashboard queries to verify the ingestion pipeline,
--          data freshness, storage footprint, and market discovery subsystem
--          are all functioning correctly. Run these first whenever something
--          "feels off" -- they answer "is data actually flowing?"
-- =============================================================================


-- ---------------------------------------------------------------------------
-- 1.1  Ingestion rates by data type (last hour)
-- ---------------------------------------------------------------------------
-- Shows rows-per-minute for each core data stream over the last 60 minutes.
-- A sudden drop to zero in any stream indicates an ingestion outage.
-- Compare across streams: trades and ticker_updates should correlate; if
-- trades are flowing but orderbook_deltas are not, the orderbook websocket
-- may have disconnected.
-- ---------------------------------------------------------------------------

WITH ingestion_rates AS (
    SELECT
        'trades' AS data_type,
        time_bucket('1 minute', ts) AS bucket,
        count(*) AS row_count
    FROM trades
    WHERE ts > now() - interval '1 hour'
    GROUP BY bucket

    UNION ALL

    SELECT
        'ticker_updates' AS data_type,
        time_bucket('1 minute', ts) AS bucket,
        count(*) AS row_count
    FROM ticker_updates
    WHERE ts > now() - interval '1 hour'
    GROUP BY bucket

    UNION ALL

    SELECT
        'orderbook_deltas' AS data_type,
        time_bucket('1 minute', ts) AS bucket,
        count(*) AS row_count
    FROM orderbook_deltas
    WHERE ts > now() - interval '1 hour'
    GROUP BY bucket

    UNION ALL

    SELECT
        'signal_log' AS data_type,
        time_bucket('1 minute', ts) AS bucket,
        count(*) AS row_count
    FROM signal_log
    WHERE ts > now() - interval '1 hour'
    GROUP BY bucket
)
SELECT
    data_type,
    count(*)                           AS minutes_with_data,
    round(avg(row_count), 1)           AS avg_rows_per_min,
    min(row_count)                     AS min_rows_per_min,
    max(row_count)                     AS max_rows_per_min,
    sum(row_count)                     AS total_rows
FROM ingestion_rates
GROUP BY data_type
ORDER BY data_type;


-- ---------------------------------------------------------------------------
-- 1.2  Data freshness: age of most recent record per table
-- ---------------------------------------------------------------------------
-- If any of these ages exceed a few minutes during market hours, the
-- corresponding pipeline is stalled. The signal_log and composite_log
-- will naturally be stale when no signals are firing, so interpret those
-- with context.
-- ---------------------------------------------------------------------------

SELECT
    'trades'            AS source,  max(ts) AS latest_ts, now() - max(ts) AS age
FROM trades
UNION ALL
SELECT
    'ticker_updates',                max(ts),             now() - max(ts)
FROM ticker_updates
UNION ALL
SELECT
    'orderbook_deltas',              max(ts),             now() - max(ts)
FROM orderbook_deltas
UNION ALL
SELECT
    'signal_log',                    max(ts),             now() - max(ts)
FROM signal_log
UNION ALL
SELECT
    'composite_log',                 max(ts),             now() - max(ts)
FROM composite_log
UNION ALL
SELECT
    'regime_log',                    max(ts),             now() - max(ts)
FROM regime_log
UNION ALL
SELECT
    'price_snapshots',               max(ts),             now() - max(ts)
FROM price_snapshots
ORDER BY source;


-- ---------------------------------------------------------------------------
-- 1.3  Table sizes (TimescaleDB hypertable stats)
-- ---------------------------------------------------------------------------
-- Tracks disk usage growth over time. If a table is growing much faster
-- than expected, check for duplicate ingestion or a misbehaving market
-- that is generating excessive orderbook churn.
-- ---------------------------------------------------------------------------

SELECT
    hypertable_name,
    num_chunks,
    pg_size_pretty(total_bytes)         AS total_size,
    pg_size_pretty(table_bytes)         AS table_size,
    pg_size_pretty(index_bytes)         AS index_size,
    pg_size_pretty(toast_bytes)         AS toast_size
FROM timescaledb_information.hypertable_size(
    (SELECT format('%I.%I', hypertable_schema, hypertable_name)::regclass
     FROM timescaledb_information.hypertables)
)
ORDER BY total_bytes DESC;

-- Simpler fallback if the above doesn't work on your TimescaleDB version:
SELECT
    hypertable_schema,
    hypertable_name,
    num_chunks,
    compression_enabled
FROM timescaledb_information.hypertables
ORDER BY hypertable_name;


-- ---------------------------------------------------------------------------
-- 1.4  Market discovery status
-- ---------------------------------------------------------------------------
-- Shows how many markets the discovery subsystem has found and their
-- current status. A healthy system should show a large "active" count
-- and some "closed"/"settled" markets accumulating over time.
-- ---------------------------------------------------------------------------

SELECT
    status,
    count(*)                            AS market_count
FROM markets
GROUP BY status
ORDER BY market_count DESC;


-- ---------------------------------------------------------------------------
-- 1.5  Gap detection: hours with suspiciously low trade counts (last 24h)
-- ---------------------------------------------------------------------------
-- Flags hourly buckets where trade volume dropped below 20% of the
-- rolling average. Gaps during overnight hours (when Kalshi markets are
-- less active) are expected; gaps during US market hours are not.
-- The threshold is intentionally conservative -- adjust the 0.20 factor
-- to suit your market universe.
-- ---------------------------------------------------------------------------

WITH hourly AS (
    SELECT
        time_bucket('1 hour', ts)       AS hour,
        count(*)                        AS trade_count
    FROM trades
    WHERE ts > now() - interval '24 hours'
    GROUP BY hour
),
stats AS (
    SELECT avg(trade_count) AS avg_count FROM hourly
)
SELECT
    h.hour,
    h.trade_count,
    round(s.avg_count, 0)              AS period_avg,
    round(h.trade_count / NULLIF(s.avg_count, 0), 3) AS ratio_to_avg,
    CASE
        WHEN h.trade_count < s.avg_count * 0.20 THEN 'SUSPICIOUS GAP'
        WHEN h.trade_count < s.avg_count * 0.50 THEN 'LOW'
        ELSE 'OK'
    END                                 AS status
FROM hourly h
CROSS JOIN stats s
ORDER BY h.hour;
