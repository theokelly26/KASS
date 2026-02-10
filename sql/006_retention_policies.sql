-- Keep raw orderbook deltas for 30 days, everything else for 1 year
-- Using DO block to handle "policy already exists" gracefully
DO $$
BEGIN
    PERFORM add_retention_policy('orderbook_deltas', INTERVAL '30 days', if_not_exists => TRUE);
    PERFORM add_retention_policy('orderbook_snapshots', INTERVAL '90 days', if_not_exists => TRUE);
    PERFORM add_retention_policy('system_health', INTERVAL '30 days', if_not_exists => TRUE);
    -- trades and ticker_updates: keep indefinitely (manual archival)
END $$;
