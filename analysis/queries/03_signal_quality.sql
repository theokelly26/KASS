-- =============================================================================
-- KASS Analysis Library: 03 - Signal Quality
-- =============================================================================
-- Purpose: THE MOST IMPORTANT FILE. These queries measure whether signals
--          actually predict future price moves. Everything else is plumbing;
--          this is the P&L. The signal_outcomes materialized view pre-joins
--          signals with subsequent price data so we can evaluate accuracy
--          across multiple horizons.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- 3.1  Hit rate by signal type (5-minute horizon) -- THE MONEY QUERY
-- ---------------------------------------------------------------------------
-- For each signal type, what fraction of signals correctly predicted the
-- direction of the 5-minute price move? A hit rate above 0.55 on binary
-- events is meaningful; above 0.60 is excellent. Below 0.50 means the
-- signal is anti-predictive (which is still useful -- just invert it).
--
-- We also show average move magnitude to distinguish signals that are
-- "correct but tiny" from those that are "correct and material."
-- ---------------------------------------------------------------------------

SELECT
    signal_type,
    direction,
    count(*)                                        AS total_signals,
    count(*) FILTER (WHERE correct_5m = true)       AS correct_5m,
    count(*) FILTER (WHERE correct_5m = false)      AS incorrect_5m,
    count(*) FILTER (WHERE correct_5m IS NULL)      AS no_data_5m,
    round(
        count(*) FILTER (WHERE correct_5m = true)::numeric
        / NULLIF(count(*) FILTER (WHERE correct_5m IS NOT NULL), 0),
        4
    )                                               AS hit_rate_5m,
    round(avg(abs(move_5m)) FILTER (WHERE move_5m IS NOT NULL), 4)
                                                    AS avg_abs_move_5m,
    round(avg(move_5m) FILTER (WHERE move_5m IS NOT NULL), 4)
                                                    AS avg_signed_move_5m
FROM signal_outcomes
GROUP BY signal_type, direction
ORDER BY hit_rate_5m DESC NULLS LAST;


-- ---------------------------------------------------------------------------
-- 3.2  Hit rate by signal type (15-minute horizon)
-- ---------------------------------------------------------------------------
-- Same analysis at 15 minutes. Comparing 5m vs 15m hit rates reveals
-- whether a signal captures a transient microstructure effect (5m high,
-- 15m lower) or a durable directional move (both high or 15m higher).
-- ---------------------------------------------------------------------------

SELECT
    signal_type,
    direction,
    count(*)                                        AS total_signals,
    count(*) FILTER (WHERE correct_15m = true)      AS correct_15m,
    count(*) FILTER (WHERE correct_15m = false)     AS incorrect_15m,
    round(
        count(*) FILTER (WHERE correct_15m = true)::numeric
        / NULLIF(count(*) FILTER (WHERE correct_15m IS NOT NULL), 0),
        4
    )                                               AS hit_rate_15m,
    round(avg(abs(move_15m)) FILTER (WHERE move_15m IS NOT NULL), 4)
                                                    AS avg_abs_move_15m,
    round(avg(move_15m) FILTER (WHERE move_15m IS NOT NULL), 4)
                                                    AS avg_signed_move_15m,
    round(avg(abs(move_60m)) FILTER (WHERE move_60m IS NOT NULL), 4)
                                                    AS avg_abs_move_60m
FROM signal_outcomes
GROUP BY signal_type, direction
ORDER BY hit_rate_15m DESC NULLS LAST;


-- ---------------------------------------------------------------------------
-- 3.3  Signal quality by strength bucket
-- ---------------------------------------------------------------------------
-- Strength is the raw magnitude of the signal. If the system is well-
-- calibrated, stronger signals should have higher hit rates. If they
-- don't, the strength calculation needs rework. We bucket into the
-- canonical labels: weak (<0.25), moderate (0.25-0.50), strong (0.50-0.75),
-- very_strong (>0.75).
-- ---------------------------------------------------------------------------

SELECT
    signal_type,
    CASE
        WHEN strength < 0.25 THEN 'weak'
        WHEN strength < 0.50 THEN 'moderate'
        WHEN strength < 0.75 THEN 'strong'
        ELSE                      'very_strong'
    END                                             AS strength_bucket,
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
    round(avg(confidence)::numeric, 4)                AS avg_confidence
FROM signal_outcomes
GROUP BY signal_type, strength_bucket
ORDER BY signal_type, strength_bucket;


-- ---------------------------------------------------------------------------
-- 3.4  Signal quality by regime
-- ---------------------------------------------------------------------------
-- Signals may perform very differently depending on the market regime
-- active at the time they fired. For example, VPIN signals may be
-- excellent in volatile regimes but noisy in calm ones. This tells you
-- when to trust each signal type.
-- ---------------------------------------------------------------------------

SELECT
    so.signal_type,
    cl.regime,
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
    round(avg(abs(so.move_15m)), 4)                 AS avg_abs_move_15m
FROM signal_outcomes so
LEFT JOIN LATERAL (
    -- Find the composite log entry closest in time to the signal
    SELECT regime
    FROM composite_log cl2
    WHERE cl2.market_ticker = so.market_ticker
      AND cl2.ts <= so.signal_ts
    ORDER BY cl2.ts DESC
    LIMIT 1
) cl ON true
GROUP BY so.signal_type, cl.regime
ORDER BY so.signal_type, hit_rate_5m DESC NULLS LAST;


-- ---------------------------------------------------------------------------
-- 3.5  Composite score vs actual outcome
-- ---------------------------------------------------------------------------
-- The composite score is the final aggregated trading signal. This query
-- buckets composite scores and measures the average subsequent price move.
-- A monotonically increasing relationship (higher composite -> larger
-- positive move, lower composite -> larger negative move) is the goal.
-- ---------------------------------------------------------------------------

SELECT
    width_bucket(cl.composite_score, -1.0, 1.0, 20) AS bucket,
    round(-1.0 + (width_bucket(cl.composite_score, -1.0, 1.0, 20) - 1) * 0.1, 2)
                                                    AS score_low,
    round(-1.0 + width_bucket(cl.composite_score, -1.0, 1.0, 20) * 0.1, 2)
                                                    AS score_high,
    count(*)                                        AS n,
    round(avg(ps_after.yes_price - ps_at.yes_price), 4)
                                                    AS avg_move_5m,
    round(avg(abs(ps_after.yes_price - ps_at.yes_price)), 4)
                                                    AS avg_abs_move_5m,
    round(
        count(*) FILTER (
            WHERE (cl.direction = 'buy_yes' AND ps_after.yes_price > ps_at.yes_price)
               OR (cl.direction = 'buy_no'  AND ps_after.yes_price < ps_at.yes_price)
        )::numeric / NULLIF(count(*), 0),
        4
    )                                               AS directional_accuracy
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
GROUP BY bucket
ORDER BY bucket;


-- ---------------------------------------------------------------------------
-- 3.6  Expected value per signal type
-- ---------------------------------------------------------------------------
-- Combines hit rate with move magnitude to estimate the expected value
-- of acting on each signal type. This is the closest thing to a
-- theoretical P&L without actual position sizing. Positive EV signals
-- are candidates for live trading; negative EV signals should be
-- disabled or inverted.
--
-- EV = (hit_rate * avg_win) - ((1 - hit_rate) * avg_loss)
-- ---------------------------------------------------------------------------

SELECT
    signal_type,
    direction,
    count(*) FILTER (WHERE correct_5m IS NOT NULL)  AS evaluated_signals,

    -- Hit rate
    round(
        count(*) FILTER (WHERE correct_5m = true)::numeric
        / NULLIF(count(*) FILTER (WHERE correct_5m IS NOT NULL), 0),
        4
    )                                               AS hit_rate_5m,

    -- Average win (move magnitude when correct)
    round(
        avg(abs(move_5m)) FILTER (WHERE correct_5m = true),
        4
    )                                               AS avg_win_5m,

    -- Average loss (move magnitude when incorrect)
    round(
        avg(abs(move_5m)) FILTER (WHERE correct_5m = false),
        4
    )                                               AS avg_loss_5m,

    -- Expected value per signal (cents)
    round(
        (count(*) FILTER (WHERE correct_5m = true)::numeric
            / NULLIF(count(*) FILTER (WHERE correct_5m IS NOT NULL), 0))
        * avg(abs(move_5m)) FILTER (WHERE correct_5m = true)
        -
        (1 - count(*) FILTER (WHERE correct_5m = true)::numeric
            / NULLIF(count(*) FILTER (WHERE correct_5m IS NOT NULL), 0))
        * avg(abs(move_5m)) FILTER (WHERE correct_5m = false),
        4
    )                                               AS ev_per_signal_5m,

    -- Same for 15-minute horizon
    round(
        count(*) FILTER (WHERE correct_15m = true)::numeric
        / NULLIF(count(*) FILTER (WHERE correct_15m IS NOT NULL), 0),
        4
    )                                               AS hit_rate_15m,

    round(
        (count(*) FILTER (WHERE correct_15m = true)::numeric
            / NULLIF(count(*) FILTER (WHERE correct_15m IS NOT NULL), 0))
        * avg(abs(move_15m)) FILTER (WHERE correct_15m = true)
        -
        (1 - count(*) FILTER (WHERE correct_15m = true)::numeric
            / NULLIF(count(*) FILTER (WHERE correct_15m IS NOT NULL), 0))
        * avg(abs(move_15m)) FILTER (WHERE correct_15m = false),
        4
    )                                               AS ev_per_signal_15m

FROM signal_outcomes
GROUP BY signal_type, direction
ORDER BY ev_per_signal_5m DESC NULLS LAST;
