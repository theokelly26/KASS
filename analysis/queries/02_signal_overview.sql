-- =============================================================================
-- KASS Analysis Library: 02 - Signal Overview
-- =============================================================================
-- Purpose: High-level view of signal production. These queries answer
--          "what is the system actually generating?" before we ask "is it
--          any good?" (that comes in 03_signal_quality.sql). Use this to
--          understand signal volume, distribution across types/markets, and
--          the regime landscape.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- 2.1  Signal count by type and direction (last 24h)
-- ---------------------------------------------------------------------------
-- The primary census of signal production. Average strength and confidence
-- tell you whether the system is firing mostly weak/tentative signals or
-- strong/confident ones. If a signal type has high volume but low avg
-- confidence, its threshold may be too loose.
-- ---------------------------------------------------------------------------

SELECT
    signal_type,
    direction,
    count(*)                                AS signal_count,
    round(avg(strength), 4)                 AS avg_strength,
    round(avg(confidence), 4)               AS avg_confidence,
    round(avg(urgency), 4)                  AS avg_urgency,
    round(min(strength), 4)                 AS min_strength,
    round(max(strength), 4)                 AS max_strength
FROM signal_log
WHERE ts > now() - interval '24 hours'
GROUP BY signal_type, direction
ORDER BY signal_count DESC;


-- ---------------------------------------------------------------------------
-- 2.2  Signal frequency by hour and type
-- ---------------------------------------------------------------------------
-- Reveals the intraday rhythm of signal generation. Some signal types
-- (e.g., VPIN) should cluster around high-activity periods; others
-- (e.g., cross-market propagation) may lag by design. Flat distributions
-- suggest noise; peaked distributions suggest the signal is picking up
-- real intraday structure.
-- ---------------------------------------------------------------------------

SELECT
    time_bucket('1 hour', ts)               AS hour,
    signal_type,
    count(*)                                AS signal_count,
    round(avg(strength), 4)                 AS avg_strength
FROM signal_log
WHERE ts > now() - interval '24 hours'
GROUP BY hour, signal_type
ORDER BY hour, signal_type;


-- ---------------------------------------------------------------------------
-- 2.3  Top 20 most-signaled markets
-- ---------------------------------------------------------------------------
-- Identifies which markets are generating the most signals. Join to
-- markets for human-readable titles. Over-concentration in a single
-- market may indicate a noisy data feed rather than genuine alpha.
-- ---------------------------------------------------------------------------

SELECT
    sl.market_ticker,
    m.title                                 AS market_title,
    m.status                                AS market_status,
    count(*)                                AS signal_count,
    count(DISTINCT sl.signal_type)          AS distinct_signal_types,
    round(avg(sl.strength), 4)              AS avg_strength,
    round(avg(sl.confidence), 4)            AS avg_confidence
FROM signal_log sl
LEFT JOIN markets m ON m.ticker = sl.market_ticker
WHERE sl.ts > now() - interval '24 hours'
GROUP BY sl.market_ticker, m.title, m.status
ORDER BY signal_count DESC
LIMIT 20;


-- ---------------------------------------------------------------------------
-- 2.4  Composite score distribution buckets
-- ---------------------------------------------------------------------------
-- The composite score aggregates multiple individual signals into a
-- single actionable number. This histogram shows the distribution.
-- A well-calibrated system should have most composites near zero
-- (noise) with fat tails only for genuine events.
-- ---------------------------------------------------------------------------

SELECT
    width_bucket(composite_score, -1.0, 1.0, 20) AS bucket,
    round(-1.0 + (width_bucket(composite_score, -1.0, 1.0, 20) - 1) * 0.1, 2)
                                            AS bucket_low,
    round(-1.0 + width_bucket(composite_score, -1.0, 1.0, 20) * 0.1, 2)
                                            AS bucket_high,
    count(*)                                AS composite_count,
    round(avg(active_signal_count), 1)      AS avg_active_signals
FROM composite_log
WHERE ts > now() - interval '24 hours'
GROUP BY bucket
ORDER BY bucket;


-- ---------------------------------------------------------------------------
-- 2.5  Regime distribution across markets (current snapshot)
-- ---------------------------------------------------------------------------
-- Shows what regime each market is currently in. "Current" is approximated
-- as the most recent regime_log entry per market. A system dominated by
-- 'low_activity' regimes during market hours may indicate stale discovery
-- or inactive markets in the universe.
-- ---------------------------------------------------------------------------

WITH latest_regime AS (
    SELECT DISTINCT ON (market_ticker)
        market_ticker,
        new_regime          AS current_regime,
        ts                  AS regime_since,
        trade_rate,
        message_rate,
        depth_imbalance
    FROM regime_log
    ORDER BY market_ticker, ts DESC
)
SELECT
    current_regime,
    count(*)                                AS market_count,
    round(avg(trade_rate), 2)               AS avg_trade_rate,
    round(avg(message_rate), 2)             AS avg_message_rate,
    round(avg(depth_imbalance), 4)          AS avg_depth_imbalance
FROM latest_regime
GROUP BY current_regime
ORDER BY market_count DESC;


-- ---------------------------------------------------------------------------
-- 2.6  Regime transitions (last 24h)
-- ---------------------------------------------------------------------------
-- Counts transitions between regimes. Frequent oscillation between two
-- regimes (e.g., normal <-> volatile) may indicate the regime detector
-- thresholds need hysteresis or smoothing.
-- ---------------------------------------------------------------------------

SELECT
    old_regime,
    new_regime,
    count(*)                                AS transition_count,
    round(avg(trade_rate), 2)               AS avg_trade_rate_at_transition,
    round(avg(message_rate), 2)             AS avg_message_rate_at_transition
FROM regime_log
WHERE ts > now() - interval '24 hours'
GROUP BY old_regime, new_regime
ORDER BY transition_count DESC;
