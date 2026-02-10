-- =============================================================================
-- KASS Analysis Library: 04 - Threshold Tuning
-- =============================================================================
-- Purpose: Parameter optimization queries. After 03_signal_quality tells you
--          WHICH signals work, these queries help you find the OPTIMAL
--          thresholds for each signal's internal parameters. The goal is to
--          maximize hit rate and EV by tuning the knobs embedded in the
--          signal metadata (VPIN thresholds, OI z-score cutoffs, etc.)
--          and the composite aggregation layer.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- 4.1  VPIN distribution with hit rates
-- ---------------------------------------------------------------------------
-- VPIN (Volume-synchronized Probability of Informed Trading) is stored
-- in signal metadata. This query buckets VPIN values and shows the hit
-- rate for each bucket. The optimal VPIN threshold is the point where
-- hit rate jumps above your profitability cutoff (typically ~0.55).
-- Signals with VPIN below that threshold are noise and should be filtered.
-- ---------------------------------------------------------------------------

WITH vpin_signals AS (
    SELECT
        so.*,
        (so.metadata->>'vpin')::numeric AS vpin_value
    FROM signal_outcomes so
    WHERE so.metadata->>'vpin' IS NOT NULL
)
SELECT
    width_bucket(vpin_value, 0.0, 1.0, 20)         AS bucket,
    round(0.0 + (width_bucket(vpin_value, 0.0, 1.0, 20) - 1) * 0.05, 2)
                                                    AS vpin_low,
    round(0.0 + width_bucket(vpin_value, 0.0, 1.0, 20) * 0.05, 2)
                                                    AS vpin_high,
    count(*)                                        AS signal_count,
    round(
        count(*) FILTER (WHERE correct_5m = true)::numeric
        / NULLIF(count(*) FILTER (WHERE correct_5m IS NOT NULL), 0),
        4
    )                                               AS hit_rate_5m,
    round(
        count(*) FILTER (WHERE correct_15m = true)::numeric
        / NULLIF(count(*) FILTER (WHERE correct_15m IS NOT NULL), 0),
        4
    )                                               AS hit_rate_15m,
    round(avg(abs(move_5m)), 4)                     AS avg_abs_move_5m,
    round(avg(abs(move_15m)), 4)                    AS avg_abs_move_15m,
    round(avg(confidence), 4)                       AS avg_confidence
FROM vpin_signals
GROUP BY bucket
ORDER BY bucket;


-- ---------------------------------------------------------------------------
-- 4.2  OI z-score distribution with hit rates
-- ---------------------------------------------------------------------------
-- Open interest velocity z-score measures how unusual the rate of OI
-- change is relative to recent history. Higher z-scores should correspond
-- to more informed flow. This query finds the z-score cutoff that
-- separates noise from signal.
-- ---------------------------------------------------------------------------

WITH oi_signals AS (
    SELECT
        so.*,
        (so.metadata->>'oi_velocity_zscore')::numeric AS oi_zscore
    FROM signal_outcomes so
    WHERE so.metadata->>'oi_velocity_zscore' IS NOT NULL
)
SELECT
    width_bucket(oi_zscore, 0.0, 5.0, 25)          AS bucket,
    round(0.0 + (width_bucket(oi_zscore, 0.0, 5.0, 25) - 1) * 0.2, 2)
                                                    AS zscore_low,
    round(0.0 + width_bucket(oi_zscore, 0.0, 5.0, 25) * 0.2, 2)
                                                    AS zscore_high,
    count(*)                                        AS signal_count,
    round(
        count(*) FILTER (WHERE correct_5m = true)::numeric
        / NULLIF(count(*) FILTER (WHERE correct_5m IS NOT NULL), 0),
        4
    )                                               AS hit_rate_5m,
    round(
        count(*) FILTER (WHERE correct_15m = true)::numeric
        / NULLIF(count(*) FILTER (WHERE correct_15m IS NOT NULL), 0),
        4
    )                                               AS hit_rate_15m,
    round(avg(abs(move_5m)), 4)                     AS avg_abs_move_5m,
    round(avg(abs(move_15m)), 4)                    AS avg_abs_move_15m,
    round(avg(strength), 4)                         AS avg_strength
FROM oi_signals
GROUP BY bucket
ORDER BY bucket;


-- ---------------------------------------------------------------------------
-- 4.3  Cross-market propagation lag analysis
-- ---------------------------------------------------------------------------
-- When a signal fires on one market in an event, how long does it take
-- for correlated markets (same event_ticker) to move? This informs the
-- TTL and urgency parameters for cross-market propagation signals.
-- We look at signal pairs within the same event and measure the time
-- delta between them.
-- ---------------------------------------------------------------------------

WITH event_signals AS (
    SELECT
        sl.ts,
        sl.signal_id,
        sl.signal_type,
        sl.market_ticker,
        sl.event_ticker,
        sl.direction,
        sl.strength
    FROM signal_log sl
    WHERE sl.event_ticker IS NOT NULL
      AND sl.ts > now() - interval '7 days'
),
signal_pairs AS (
    SELECT
        a.event_ticker,
        a.signal_type,
        a.market_ticker                             AS source_market,
        b.market_ticker                             AS target_market,
        a.ts                                        AS source_ts,
        b.ts                                        AS target_ts,
        extract(epoch FROM b.ts - a.ts)             AS lag_seconds,
        a.direction                                 AS source_direction,
        b.direction                                 AS target_direction
    FROM event_signals a
    JOIN event_signals b
        ON  a.event_ticker = b.event_ticker
        AND a.market_ticker <> b.market_ticker
        AND b.ts > a.ts
        AND b.ts < a.ts + interval '30 minutes'
)
SELECT
    signal_type,
    count(*)                                        AS pair_count,
    round(avg(lag_seconds), 1)                      AS avg_lag_sec,
    round(percentile_cont(0.25) WITHIN GROUP (ORDER BY lag_seconds), 1)
                                                    AS p25_lag_sec,
    round(percentile_cont(0.50) WITHIN GROUP (ORDER BY lag_seconds), 1)
                                                    AS median_lag_sec,
    round(percentile_cont(0.75) WITHIN GROUP (ORDER BY lag_seconds), 1)
                                                    AS p75_lag_sec,
    round(percentile_cont(0.95) WITHIN GROUP (ORDER BY lag_seconds), 1)
                                                    AS p95_lag_sec,
    round(
        count(*) FILTER (WHERE source_direction = target_direction)::numeric
        / NULLIF(count(*), 0),
        4
    )                                               AS same_direction_rate
FROM signal_pairs
GROUP BY signal_type
ORDER BY avg_lag_sec;


-- ---------------------------------------------------------------------------
-- 4.4  Optimal composite threshold sweep
-- ---------------------------------------------------------------------------
-- Sweeps composite_score thresholds from 0.10 to 0.90 in steps of 0.05
-- and evaluates the hit rate and expected value at each threshold. This
-- directly answers "what composite score should I require before trading?"
-- Higher thresholds = fewer but higher-quality signals.
-- ---------------------------------------------------------------------------

WITH thresholds AS (
    SELECT generate_series(0.10, 0.90, 0.05) AS threshold
),
composite_outcomes AS (
    SELECT
        cl.ts,
        cl.market_ticker,
        cl.composite_score,
        cl.direction,
        ps_after.yes_price - ps_at.yes_price        AS move_5m,
        CASE
            WHEN cl.direction = 'yes' AND ps_after.yes_price > ps_at.yes_price THEN true
            WHEN cl.direction = 'no'  AND ps_after.yes_price < ps_at.yes_price THEN true
            WHEN ps_after.yes_price = ps_at.yes_price THEN NULL
            ELSE false
        END                                         AS correct_5m
    FROM composite_log cl
    LEFT JOIN LATERAL (
        SELECT yes_price
        FROM price_snapshots
        WHERE market_ticker = cl.market_ticker
          AND ts >= cl.ts
        ORDER BY ts ASC
        LIMIT 1
    ) ps_at ON true
    LEFT JOIN LATERAL (
        SELECT yes_price
        FROM price_snapshots
        WHERE market_ticker = cl.market_ticker
          AND ts >= cl.ts + interval '5 minutes'
        ORDER BY ts ASC
        LIMIT 1
    ) ps_after ON true
    WHERE ps_at.yes_price IS NOT NULL
      AND ps_after.yes_price IS NOT NULL
)
SELECT
    t.threshold,
    count(*) FILTER (WHERE abs(co.composite_score) >= t.threshold)
                                                    AS signals_above_threshold,
    round(
        count(*) FILTER (
            WHERE abs(co.composite_score) >= t.threshold
              AND co.correct_5m = true
        )::numeric
        / NULLIF(
            count(*) FILTER (
                WHERE abs(co.composite_score) >= t.threshold
                  AND co.correct_5m IS NOT NULL
            ), 0
        ),
        4
    )                                               AS hit_rate_5m,
    round(
        avg(abs(co.move_5m)) FILTER (
            WHERE abs(co.composite_score) >= t.threshold
              AND co.correct_5m = true
        ),
        4
    )                                               AS avg_win_5m,
    round(
        avg(abs(co.move_5m)) FILTER (
            WHERE abs(co.composite_score) >= t.threshold
              AND co.correct_5m = false
        ),
        4
    )                                               AS avg_loss_5m,
    round(
        avg(co.move_5m) FILTER (
            WHERE abs(co.composite_score) >= t.threshold
        ),
        4
    )                                               AS avg_signed_move_5m
FROM thresholds t
CROSS JOIN composite_outcomes co
GROUP BY t.threshold
ORDER BY t.threshold;


-- ---------------------------------------------------------------------------
-- 4.5  Category performance by series
-- ---------------------------------------------------------------------------
-- Different series (election, crypto, weather, sports, etc.) may have
-- fundamentally different signal characteristics. A VPIN signal on a
-- crypto market may behave nothing like a VPIN signal on a weather
-- market. This query breaks down signal performance by series so you
-- can tune thresholds per-category or disable signals for series where
-- they don't work.
-- ---------------------------------------------------------------------------

SELECT
    s.title                                         AS series_title,
    so.signal_type,
    count(*)                                        AS signal_count,
    round(
        count(*) FILTER (WHERE so.correct_5m = true)::numeric
        / NULLIF(count(*) FILTER (WHERE so.correct_5m IS NOT NULL), 0),
        4
    )                                               AS hit_rate_5m,
    round(
        count(*) FILTER (WHERE so.correct_15m = true)::numeric
        / NULLIF(count(*) FILTER (WHERE so.correct_15m IS NOT NULL), 0),
        4
    )                                               AS hit_rate_15m,
    round(avg(abs(so.move_5m)), 4)                  AS avg_abs_move_5m,
    round(avg(abs(so.move_15m)), 4)                 AS avg_abs_move_15m,

    -- EV calculation (5m horizon)
    round(
        COALESCE(
            (count(*) FILTER (WHERE so.correct_5m = true)::numeric
                / NULLIF(count(*) FILTER (WHERE so.correct_5m IS NOT NULL), 0))
            * avg(abs(so.move_5m)) FILTER (WHERE so.correct_5m = true)
            -
            (1 - count(*) FILTER (WHERE so.correct_5m = true)::numeric
                / NULLIF(count(*) FILTER (WHERE so.correct_5m IS NOT NULL), 0))
            * avg(abs(so.move_5m)) FILTER (WHERE so.correct_5m = false),
            0
        ),
        4
    )                                               AS ev_per_signal_5m
FROM signal_outcomes so
JOIN signal_log sl ON sl.signal_id = so.signal_id
LEFT JOIN markets m ON m.ticker = so.market_ticker
LEFT JOIN series s ON s.ticker = m.series_ticker
GROUP BY s.title, so.signal_type
HAVING count(*) >= 10  -- minimum sample size for meaningful stats
ORDER BY s.title, ev_per_signal_5m DESC NULLS LAST;
