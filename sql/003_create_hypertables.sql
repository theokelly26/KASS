-- Convert time-series tables to hypertables
-- Using IF NOT EXISTS pattern via exception handling
DO $$
BEGIN
    PERFORM create_hypertable('trades', 'ts', if_not_exists => TRUE);
    PERFORM create_hypertable('ticker_updates', 'ts', if_not_exists => TRUE);
    PERFORM create_hypertable('orderbook_snapshots', 'ts', if_not_exists => TRUE);
    PERFORM create_hypertable('orderbook_deltas', 'ts', if_not_exists => TRUE);
    PERFORM create_hypertable('lifecycle_events', 'ts', if_not_exists => TRUE);
    PERFORM create_hypertable('system_health', 'ts', if_not_exists => TRUE);
END $$;
