-- Materialized view: latest state per market
CREATE MATERIALIZED VIEW IF NOT EXISTS market_latest AS
SELECT DISTINCT ON (market_ticker)
    market_ticker,
    price as last_price,
    ts as last_update
FROM ticker_updates
ORDER BY market_ticker, ts DESC;

-- View: trade volume by market by hour
CREATE OR REPLACE VIEW hourly_volume AS
SELECT
    time_bucket('1 hour', ts) AS hour,
    market_ticker,
    COUNT(*) as trade_count,
    SUM(count) as contract_volume,
    SUM(count * yes_price) as dollar_volume_approx,
    MIN(yes_price) as low,
    MAX(yes_price) as high
FROM trades
GROUP BY hour, market_ticker;

-- View: OI running total per market
CREATE OR REPLACE VIEW oi_by_market AS
SELECT
    market_ticker,
    SUM(open_interest_delta) as total_oi_delta,
    MAX(ts) as last_update
FROM ticker_updates
WHERE open_interest_delta IS NOT NULL
GROUP BY market_ticker;
