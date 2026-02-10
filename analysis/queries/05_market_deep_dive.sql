-- =============================================================================
-- KASS Analysis Library: 05 - Market Deep Dive
-- =============================================================================
-- Purpose: Drilldown queries for investigating a single market in detail.
--          Use these after the overview queries identify an interesting
--          market (high signal volume, unusual regime behavior, etc.).
--          Replace 'MARKET-TICKER-HERE' with the actual market ticker.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- 5.1  Full signal history for a market
-- ---------------------------------------------------------------------------
-- Complete timeline of every signal fired for this market, with metadata.
-- Read chronologically to understand the narrative: what did the system
-- "see" and in what order? Cross-reference with the trade tape (5.2)
-- to see if signals preceded visible price moves.
-- ---------------------------------------------------------------------------

SELECT
    sl.ts,
    sl.signal_id,
    sl.signal_type,
    sl.direction,
    sl.strength,
    sl.confidence,
    sl.urgency,
    sl.ttl_seconds,
    sl.expired_at,
    sl.metadata,
    -- Include outcome data if available
    so.price_at_signal,
    so.price_1m_after,
    so.price_5m_after,
    so.price_15m_after,
    so.price_60m_after,
    so.correct_5m,
    so.correct_15m,
    so.move_5m,
    so.move_15m,
    so.move_60m
FROM signal_log sl
LEFT JOIN signal_outcomes so ON so.signal_id = sl.signal_id
WHERE sl.market_ticker = 'MARKET-TICKER-HERE'
ORDER BY sl.ts DESC;


-- ---------------------------------------------------------------------------
-- 5.2  Trade tape for a market
-- ---------------------------------------------------------------------------
-- Raw trade-by-trade history. Look for clusters of aggressive buying
-- (taker_side = 'yes') or selling (taker_side = 'no') that correspond
-- to signal timestamps. The 'count' field shows the number of contracts
-- in each trade; large counts are institutional-sized.
-- Use time_bucket for a summary view when the tape is very long.
-- ---------------------------------------------------------------------------

-- Detailed tape (last 4 hours)
SELECT
    ts,
    trade_id,
    yes_price,
    no_price,
    count,
    taker_side
FROM trades
WHERE market_ticker = 'MARKET-TICKER-HERE'
  AND ts > now() - interval '4 hours'
ORDER BY ts DESC;

-- Aggregated tape (1-minute buckets, last 24 hours)
SELECT
    time_bucket('1 minute', ts)                     AS bucket,
    count(*)                                        AS trade_count,
    sum(count)                                      AS total_contracts,
    round(avg(yes_price), 2)                        AS avg_yes_price,
    min(yes_price)                                  AS min_yes_price,
    max(yes_price)                                  AS max_yes_price,
    sum(count) FILTER (WHERE taker_side = 'yes')    AS yes_taker_contracts,
    sum(count) FILTER (WHERE taker_side = 'no')     AS no_taker_contracts,
    round(
        sum(count) FILTER (WHERE taker_side = 'yes')::numeric
        / NULLIF(sum(count), 0),
        4
    )                                               AS buy_ratio
FROM trades
WHERE market_ticker = 'MARKET-TICKER-HERE'
  AND ts > now() - interval '24 hours'
GROUP BY bucket
ORDER BY bucket;


-- ---------------------------------------------------------------------------
-- 5.3  OI trajectory for a market
-- ---------------------------------------------------------------------------
-- Open interest (OI) changes reveal whether new money is entering
-- (OI rising) or positions are being closed (OI falling). Dollar OI
-- gives the notional value. Combine with price direction:
--   - Price up + OI up   = new longs (bullish conviction)
--   - Price up + OI down = short covering (weaker)
--   - Price down + OI up = new shorts (bearish conviction)
--   - Price down + OI down = long liquidation (weaker)
-- ---------------------------------------------------------------------------

SELECT
    time_bucket('5 minutes', ts)                    AS bucket,
    round(avg(price), 2)                            AS avg_price,
    sum(volume_delta)                               AS volume,
    sum(open_interest_delta)                        AS oi_change,
    sum(dollar_volume_delta)                        AS dollar_volume,
    sum(dollar_open_interest_delta)                 AS dollar_oi_change,
    -- Cumulative OI (running sum)
    sum(sum(open_interest_delta)) OVER (ORDER BY time_bucket('5 minutes', ts))
                                                    AS cumulative_oi_change,
    sum(sum(dollar_open_interest_delta)) OVER (ORDER BY time_bucket('5 minutes', ts))
                                                    AS cumulative_dollar_oi_change
FROM ticker_updates
WHERE market_ticker = 'MARKET-TICKER-HERE'
  AND ts > now() - interval '24 hours'
GROUP BY bucket
ORDER BY bucket;


-- ---------------------------------------------------------------------------
-- 5.4  Regime history for a market
-- ---------------------------------------------------------------------------
-- Shows every regime transition for this market. Long stretches in one
-- regime indicate stable conditions; rapid oscillation indicates the
-- regime detector may be noisy for this market. The trade_rate and
-- message_rate columns show what triggered the transition.
-- ---------------------------------------------------------------------------

SELECT
    ts,
    old_regime,
    new_regime,
    trade_rate,
    message_rate,
    depth_imbalance,
    -- Duration in this regime (time until next transition)
    lead(ts) OVER (ORDER BY ts) - ts                AS regime_duration
FROM regime_log
WHERE market_ticker = 'MARKET-TICKER-HERE'
ORDER BY ts DESC;


-- ---------------------------------------------------------------------------
-- 5.5  All composites for a market
-- ---------------------------------------------------------------------------
-- The composite log shows the final aggregated score and which individual
-- signals contributed to it. The active_signal_ids array lets you trace
-- back to specific signal_log entries. Look for composites with high
-- absolute scores -- those are the moments the system had highest
-- conviction.
-- ---------------------------------------------------------------------------

SELECT
    ts,
    direction,
    composite_score,
    regime,
    active_signal_count,
    active_signal_ids
FROM composite_log
WHERE market_ticker = 'MARKET-TICKER-HERE'
ORDER BY ts DESC;

-- Composite score over time (5-minute buckets for charting)
SELECT
    time_bucket('5 minutes', ts)                    AS bucket,
    round(avg(composite_score), 4)                  AS avg_composite,
    round(max(composite_score), 4)                  AS max_composite,
    round(min(composite_score), 4)                  AS min_composite,
    round(avg(active_signal_count), 1)              AS avg_active_signals,
    max(active_signal_count)                        AS max_active_signals
FROM composite_log
WHERE market_ticker = 'MARKET-TICKER-HERE'
  AND ts > now() - interval '24 hours'
GROUP BY bucket
ORDER BY bucket;
