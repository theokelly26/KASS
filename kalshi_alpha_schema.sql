--
-- PostgreSQL database dump
--

\restrict 4mPJ0Y7hS1NokgeU3V1CNbNSWiWTnejGekUyujfBnIE4Xbzp43xEBahMgeoEGcj

-- Dumped from database version 17.7 (Homebrew)
-- Dumped by pg_dump version 17.7 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: timescaledb; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS timescaledb WITH SCHEMA public;


--
-- Name: EXTENSION timescaledb; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION timescaledb IS 'Enables scalable inserts and complex queries for time-series data (Community Edition)';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: _compressed_hypertable_11; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._compressed_hypertable_11 (
);


ALTER TABLE _timescaledb_internal._compressed_hypertable_11 OWNER TO theokelly;

--
-- Name: _compressed_hypertable_12; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._compressed_hypertable_12 (
);


ALTER TABLE _timescaledb_internal._compressed_hypertable_12 OWNER TO theokelly;

--
-- Name: _compressed_hypertable_13; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._compressed_hypertable_13 (
);


ALTER TABLE _timescaledb_internal._compressed_hypertable_13 OWNER TO theokelly;

--
-- Name: _compressed_hypertable_14; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._compressed_hypertable_14 (
);


ALTER TABLE _timescaledb_internal._compressed_hypertable_14 OWNER TO theokelly;

--
-- Name: _compressed_hypertable_15; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._compressed_hypertable_15 (
);


ALTER TABLE _timescaledb_internal._compressed_hypertable_15 OWNER TO theokelly;

--
-- Name: _compressed_hypertable_16; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._compressed_hypertable_16 (
);


ALTER TABLE _timescaledb_internal._compressed_hypertable_16 OWNER TO theokelly;

--
-- Name: price_snapshots; Type: TABLE; Schema: public; Owner: theokelly
--

CREATE TABLE public.price_snapshots (
    ts timestamp with time zone NOT NULL,
    market_ticker text NOT NULL,
    yes_price smallint,
    yes_bid smallint,
    yes_ask smallint,
    spread smallint,
    volume_24h integer,
    open_interest integer,
    received_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.price_snapshots OWNER TO theokelly;

--
-- Name: _hyper_10_30_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_10_30_chunk (
    CONSTRAINT constraint_26 CHECK (((ts >= '2026-02-11 19:00:00-05'::timestamp with time zone) AND (ts < '2026-02-18 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.price_snapshots);


ALTER TABLE _timescaledb_internal._hyper_10_30_chunk OWNER TO theokelly;

--
-- Name: trades; Type: TABLE; Schema: public; Owner: theokelly
--

CREATE TABLE public.trades (
    ts timestamp with time zone NOT NULL,
    trade_id text NOT NULL,
    market_ticker text NOT NULL,
    yes_price smallint NOT NULL,
    no_price smallint NOT NULL,
    count numeric(12,2) NOT NULL,
    taker_side text NOT NULL,
    received_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.trades OWNER TO theokelly;

--
-- Name: _hyper_1_25_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_1_25_chunk (
    CONSTRAINT constraint_21 CHECK (((ts >= '2026-02-11 19:00:00-05'::timestamp with time zone) AND (ts < '2026-02-18 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.trades);


ALTER TABLE _timescaledb_internal._hyper_1_25_chunk OWNER TO theokelly;

--
-- Name: ticker_updates; Type: TABLE; Schema: public; Owner: theokelly
--

CREATE TABLE public.ticker_updates (
    ts timestamp with time zone NOT NULL,
    market_ticker text NOT NULL,
    price smallint,
    volume_delta numeric(12,2),
    open_interest_delta numeric(12,2),
    dollar_volume_delta integer,
    dollar_open_interest_delta integer,
    received_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.ticker_updates OWNER TO theokelly;

--
-- Name: _hyper_2_26_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_2_26_chunk (
    CONSTRAINT constraint_22 CHECK (((ts >= '2026-02-11 19:00:00-05'::timestamp with time zone) AND (ts < '2026-02-18 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.ticker_updates);


ALTER TABLE _timescaledb_internal._hyper_2_26_chunk OWNER TO theokelly;

--
-- Name: orderbook_snapshots; Type: TABLE; Schema: public; Owner: theokelly
--

CREATE TABLE public.orderbook_snapshots (
    ts timestamp with time zone NOT NULL,
    market_ticker text NOT NULL,
    yes_levels jsonb NOT NULL,
    no_levels jsonb NOT NULL,
    spread smallint,
    yes_depth_5 integer,
    no_depth_5 integer,
    received_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.orderbook_snapshots OWNER TO theokelly;

--
-- Name: _hyper_3_28_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_3_28_chunk (
    CONSTRAINT constraint_24 CHECK (((ts >= '2026-02-11 19:00:00-05'::timestamp with time zone) AND (ts < '2026-02-18 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.orderbook_snapshots);


ALTER TABLE _timescaledb_internal._hyper_3_28_chunk OWNER TO theokelly;

--
-- Name: orderbook_deltas; Type: TABLE; Schema: public; Owner: theokelly
--

CREATE TABLE public.orderbook_deltas (
    ts timestamp with time zone NOT NULL,
    market_ticker text NOT NULL,
    price smallint NOT NULL,
    delta numeric(12,2) NOT NULL,
    side text NOT NULL,
    is_own_order boolean DEFAULT false NOT NULL,
    received_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.orderbook_deltas OWNER TO theokelly;

--
-- Name: _hyper_4_24_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_4_24_chunk (
    CONSTRAINT constraint_20 CHECK (((ts >= '2026-02-11 19:00:00-05'::timestamp with time zone) AND (ts < '2026-02-18 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.orderbook_deltas);


ALTER TABLE _timescaledb_internal._hyper_4_24_chunk OWNER TO theokelly;

--
-- Name: lifecycle_events; Type: TABLE; Schema: public; Owner: theokelly
--

CREATE TABLE public.lifecycle_events (
    ts timestamp with time zone NOT NULL,
    market_ticker text NOT NULL,
    market_id text,
    status text NOT NULL,
    received_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.lifecycle_events OWNER TO theokelly;

--
-- Name: _hyper_5_10_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_5_10_chunk (
    CONSTRAINT constraint_10 CHECK (((ts >= '2026-02-25 19:00:00-05'::timestamp with time zone) AND (ts < '2026-03-04 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.lifecycle_events);


ALTER TABLE _timescaledb_internal._hyper_5_10_chunk OWNER TO theokelly;

--
-- Name: _hyper_5_11_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_5_11_chunk (
    CONSTRAINT constraint_11 CHECK (((ts >= '2026-02-18 19:00:00-05'::timestamp with time zone) AND (ts < '2026-02-25 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.lifecycle_events);


ALTER TABLE _timescaledb_internal._hyper_5_11_chunk OWNER TO theokelly;

--
-- Name: _hyper_5_14_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_5_14_chunk (
    CONSTRAINT constraint_14 CHECK (((ts >= '2026-04-08 20:00:00-04'::timestamp with time zone) AND (ts < '2026-04-15 20:00:00-04'::timestamp with time zone)))
)
INHERITS (public.lifecycle_events);


ALTER TABLE _timescaledb_internal._hyper_5_14_chunk OWNER TO theokelly;

--
-- Name: _hyper_5_15_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_5_15_chunk (
    CONSTRAINT constraint_15 CHECK (((ts >= '2026-02-11 19:00:00-05'::timestamp with time zone) AND (ts < '2026-02-18 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.lifecycle_events);


ALTER TABLE _timescaledb_internal._hyper_5_15_chunk OWNER TO theokelly;

--
-- Name: _hyper_5_16_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_5_16_chunk (
    CONSTRAINT constraint_16 CHECK (((ts >= '2026-07-01 20:00:00-04'::timestamp with time zone) AND (ts < '2026-07-08 20:00:00-04'::timestamp with time zone)))
)
INHERITS (public.lifecycle_events);


ALTER TABLE _timescaledb_internal._hyper_5_16_chunk OWNER TO theokelly;

--
-- Name: _hyper_5_21_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_5_21_chunk (
    CONSTRAINT constraint_17 CHECK (((ts >= '2027-10-27 20:00:00-04'::timestamp with time zone) AND (ts < '2027-11-03 20:00:00-04'::timestamp with time zone)))
)
INHERITS (public.lifecycle_events);


ALTER TABLE _timescaledb_internal._hyper_5_21_chunk OWNER TO theokelly;

--
-- Name: _hyper_5_31_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_5_31_chunk (
    CONSTRAINT constraint_27 CHECK (((ts >= '2026-10-28 20:00:00-04'::timestamp with time zone) AND (ts < '2026-11-04 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.lifecycle_events);


ALTER TABLE _timescaledb_internal._hyper_5_31_chunk OWNER TO theokelly;

--
-- Name: _hyper_5_32_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_5_32_chunk (
    CONSTRAINT constraint_28 CHECK (((ts >= '2026-03-25 20:00:00-04'::timestamp with time zone) AND (ts < '2026-04-01 20:00:00-04'::timestamp with time zone)))
)
INHERITS (public.lifecycle_events);


ALTER TABLE _timescaledb_internal._hyper_5_32_chunk OWNER TO theokelly;

--
-- Name: _hyper_5_33_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_5_33_chunk (
    CONSTRAINT constraint_29 CHECK (((ts >= '2026-12-30 19:00:00-05'::timestamp with time zone) AND (ts < '2027-01-06 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.lifecycle_events);


ALTER TABLE _timescaledb_internal._hyper_5_33_chunk OWNER TO theokelly;

--
-- Name: _hyper_5_34_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_5_34_chunk (
    CONSTRAINT constraint_30 CHECK (((ts >= '2027-12-29 19:00:00-05'::timestamp with time zone) AND (ts < '2028-01-05 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.lifecycle_events);


ALTER TABLE _timescaledb_internal._hyper_5_34_chunk OWNER TO theokelly;

--
-- Name: _hyper_5_35_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_5_35_chunk (
    CONSTRAINT constraint_31 CHECK (((ts >= '2026-03-04 19:00:00-05'::timestamp with time zone) AND (ts < '2026-03-11 20:00:00-04'::timestamp with time zone)))
)
INHERITS (public.lifecycle_events);


ALTER TABLE _timescaledb_internal._hyper_5_35_chunk OWNER TO theokelly;

--
-- Name: _hyper_5_36_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_5_36_chunk (
    CONSTRAINT constraint_32 CHECK (((ts >= '2026-12-23 19:00:00-05'::timestamp with time zone) AND (ts < '2026-12-30 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.lifecycle_events);


ALTER TABLE _timescaledb_internal._hyper_5_36_chunk OWNER TO theokelly;

--
-- Name: _hyper_5_37_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_5_37_chunk (
    CONSTRAINT constraint_33 CHECK (((ts >= '2026-03-11 20:00:00-04'::timestamp with time zone) AND (ts < '2026-03-18 20:00:00-04'::timestamp with time zone)))
)
INHERITS (public.lifecycle_events);


ALTER TABLE _timescaledb_internal._hyper_5_37_chunk OWNER TO theokelly;

--
-- Name: _hyper_5_38_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_5_38_chunk (
    CONSTRAINT constraint_34 CHECK (((ts >= '2026-07-29 20:00:00-04'::timestamp with time zone) AND (ts < '2026-08-05 20:00:00-04'::timestamp with time zone)))
)
INHERITS (public.lifecycle_events);


ALTER TABLE _timescaledb_internal._hyper_5_38_chunk OWNER TO theokelly;

--
-- Name: _hyper_5_39_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_5_39_chunk (
    CONSTRAINT constraint_35 CHECK (((ts >= '2026-04-22 20:00:00-04'::timestamp with time zone) AND (ts < '2026-04-29 20:00:00-04'::timestamp with time zone)))
)
INHERITS (public.lifecycle_events);


ALTER TABLE _timescaledb_internal._hyper_5_39_chunk OWNER TO theokelly;

--
-- Name: _hyper_5_40_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_5_40_chunk (
    CONSTRAINT constraint_36 CHECK (((ts >= '2026-06-17 20:00:00-04'::timestamp with time zone) AND (ts < '2026-06-24 20:00:00-04'::timestamp with time zone)))
)
INHERITS (public.lifecycle_events);


ALTER TABLE _timescaledb_internal._hyper_5_40_chunk OWNER TO theokelly;

--
-- Name: _hyper_5_41_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_5_41_chunk (
    CONSTRAINT constraint_37 CHECK (((ts >= '2030-12-25 19:00:00-05'::timestamp with time zone) AND (ts < '2031-01-01 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.lifecycle_events);


ALTER TABLE _timescaledb_internal._hyper_5_41_chunk OWNER TO theokelly;

--
-- Name: _hyper_5_9_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_5_9_chunk (
    CONSTRAINT constraint_9 CHECK (((ts >= '2026-02-04 19:00:00-05'::timestamp with time zone) AND (ts < '2026-02-11 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.lifecycle_events);


ALTER TABLE _timescaledb_internal._hyper_5_9_chunk OWNER TO theokelly;

--
-- Name: system_health; Type: TABLE; Schema: public; Owner: theokelly
--

CREATE TABLE public.system_health (
    ts timestamp with time zone DEFAULT now() NOT NULL,
    component text NOT NULL,
    status text NOT NULL,
    details jsonb,
    message_rate real,
    lag_ms real
);


ALTER TABLE public.system_health OWNER TO theokelly;

--
-- Name: _hyper_6_29_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_6_29_chunk (
    CONSTRAINT constraint_25 CHECK (((ts >= '2026-02-11 19:00:00-05'::timestamp with time zone) AND (ts < '2026-02-18 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.system_health);


ALTER TABLE _timescaledb_internal._hyper_6_29_chunk OWNER TO theokelly;

--
-- Name: _hyper_6_2_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_6_2_chunk (
    CONSTRAINT constraint_2 CHECK (((ts >= '2026-02-04 19:00:00-05'::timestamp with time zone) AND (ts < '2026-02-11 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.system_health);


ALTER TABLE _timescaledb_internal._hyper_6_2_chunk OWNER TO theokelly;

--
-- Name: signal_log; Type: TABLE; Schema: public; Owner: theokelly
--

CREATE TABLE public.signal_log (
    ts timestamp with time zone NOT NULL,
    signal_id text NOT NULL,
    signal_type text NOT NULL,
    market_ticker text NOT NULL,
    event_ticker text,
    series_ticker text,
    direction text NOT NULL,
    strength real NOT NULL,
    confidence real NOT NULL,
    urgency text NOT NULL,
    metadata jsonb,
    ttl_seconds integer NOT NULL,
    expired_at timestamp with time zone,
    received_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.signal_log OWNER TO theokelly;

--
-- Name: _hyper_7_22_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_7_22_chunk (
    CONSTRAINT constraint_19 CHECK (((ts >= '2026-02-11 19:00:00-05'::timestamp with time zone) AND (ts < '2026-02-18 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.signal_log);


ALTER TABLE _timescaledb_internal._hyper_7_22_chunk OWNER TO theokelly;

--
-- Name: composite_log; Type: TABLE; Schema: public; Owner: theokelly
--

CREATE TABLE public.composite_log (
    ts timestamp with time zone NOT NULL,
    market_ticker text NOT NULL,
    event_ticker text,
    series_ticker text,
    direction text NOT NULL,
    composite_score real NOT NULL,
    regime text NOT NULL,
    active_signal_count integer NOT NULL,
    active_signal_ids text[],
    received_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.composite_log OWNER TO theokelly;

--
-- Name: _hyper_8_27_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_8_27_chunk (
    CONSTRAINT constraint_23 CHECK (((ts >= '2026-02-11 19:00:00-05'::timestamp with time zone) AND (ts < '2026-02-18 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.composite_log);


ALTER TABLE _timescaledb_internal._hyper_8_27_chunk OWNER TO theokelly;

--
-- Name: _hyper_8_7_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_8_7_chunk (
    CONSTRAINT constraint_7 CHECK (((ts >= '2026-02-04 19:00:00-05'::timestamp with time zone) AND (ts < '2026-02-11 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.composite_log);


ALTER TABLE _timescaledb_internal._hyper_8_7_chunk OWNER TO theokelly;

--
-- Name: regime_log; Type: TABLE; Schema: public; Owner: theokelly
--

CREATE TABLE public.regime_log (
    ts timestamp with time zone NOT NULL,
    market_ticker text NOT NULL,
    old_regime text,
    new_regime text NOT NULL,
    trade_rate real,
    message_rate real,
    depth_imbalance real,
    received_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.regime_log OWNER TO theokelly;

--
-- Name: _hyper_9_23_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_9_23_chunk (
    CONSTRAINT constraint_18 CHECK (((ts >= '2026-02-11 19:00:00-05'::timestamp with time zone) AND (ts < '2026-02-18 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.regime_log);


ALTER TABLE _timescaledb_internal._hyper_9_23_chunk OWNER TO theokelly;

--
-- Name: _hyper_9_5_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE TABLE _timescaledb_internal._hyper_9_5_chunk (
    CONSTRAINT constraint_5 CHECK (((ts >= '2026-02-04 19:00:00-05'::timestamp with time zone) AND (ts < '2026-02-11 19:00:00-05'::timestamp with time zone)))
)
INHERITS (public.regime_log);


ALTER TABLE _timescaledb_internal._hyper_9_5_chunk OWNER TO theokelly;

--
-- Name: events; Type: TABLE; Schema: public; Owner: theokelly
--

CREATE TABLE public.events (
    ticker text NOT NULL,
    series_ticker text NOT NULL,
    title text,
    status text,
    market_count integer,
    last_synced_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.events OWNER TO theokelly;

--
-- Name: hourly_volume; Type: VIEW; Schema: public; Owner: theokelly
--

CREATE VIEW public.hourly_volume AS
 SELECT public.time_bucket('01:00:00'::interval, ts) AS hour,
    market_ticker,
    count(*) AS trade_count,
    sum(count) AS contract_volume,
    sum((count * (yes_price)::numeric)) AS dollar_volume_approx,
    min(yes_price) AS low,
    max(yes_price) AS high
   FROM public.trades
  GROUP BY (public.time_bucket('01:00:00'::interval, ts)), market_ticker;


ALTER VIEW public.hourly_volume OWNER TO theokelly;

--
-- Name: market_latest; Type: MATERIALIZED VIEW; Schema: public; Owner: theokelly
--

CREATE MATERIALIZED VIEW public.market_latest AS
 SELECT DISTINCT ON (market_ticker) market_ticker,
    price AS last_price,
    ts AS last_update
   FROM public.ticker_updates
  ORDER BY market_ticker, ts DESC
  WITH NO DATA;


ALTER MATERIALIZED VIEW public.market_latest OWNER TO theokelly;

--
-- Name: markets; Type: TABLE; Schema: public; Owner: theokelly
--

CREATE TABLE public.markets (
    ticker text NOT NULL,
    event_ticker text NOT NULL,
    series_ticker text,
    title text NOT NULL,
    subtitle text,
    status text NOT NULL,
    market_type text,
    close_time timestamp with time zone,
    result text,
    last_synced_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.markets OWNER TO theokelly;

--
-- Name: oi_by_market; Type: VIEW; Schema: public; Owner: theokelly
--

CREATE VIEW public.oi_by_market AS
 SELECT market_ticker,
    sum(open_interest_delta) AS total_oi_delta,
    max(ts) AS last_update
   FROM public.ticker_updates
  WHERE (open_interest_delta IS NOT NULL)
  GROUP BY market_ticker;


ALTER VIEW public.oi_by_market OWNER TO theokelly;

--
-- Name: series; Type: TABLE; Schema: public; Owner: theokelly
--

CREATE TABLE public.series (
    ticker text NOT NULL,
    title text,
    category text,
    tags text[],
    last_synced_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.series OWNER TO theokelly;

--
-- Name: signal_outcomes; Type: MATERIALIZED VIEW; Schema: public; Owner: theokelly
--

CREATE MATERIALIZED VIEW public.signal_outcomes AS
 SELECT s.signal_id,
    s.signal_type,
    s.market_ticker,
    s.direction,
    s.strength,
    s.confidence,
    s.metadata,
    s.ts AS signal_ts,
    p_at.yes_price AS price_at_signal,
    p_1m.yes_price AS price_1m_after,
    p_5m.yes_price AS price_5m_after,
    p_15m.yes_price AS price_15m_after,
    p_60m.yes_price AS price_60m_after,
        CASE
            WHEN ((s.direction = 'buy_yes'::text) AND (p_5m.yes_price > p_at.yes_price)) THEN true
            WHEN ((s.direction = 'buy_no'::text) AND (p_5m.yes_price < p_at.yes_price)) THEN true
            WHEN (s.direction = 'neutral'::text) THEN NULL::boolean
            ELSE false
        END AS correct_5m,
        CASE
            WHEN ((s.direction = 'buy_yes'::text) AND (p_15m.yes_price > p_at.yes_price)) THEN true
            WHEN ((s.direction = 'buy_no'::text) AND (p_15m.yes_price < p_at.yes_price)) THEN true
            WHEN (s.direction = 'neutral'::text) THEN NULL::boolean
            ELSE false
        END AS correct_15m,
    COALESCE(((p_5m.yes_price - p_at.yes_price))::integer, 0) AS move_5m,
    COALESCE(((p_15m.yes_price - p_at.yes_price))::integer, 0) AS move_15m,
    COALESCE(((p_60m.yes_price - p_at.yes_price))::integer, 0) AS move_60m
   FROM (((((public.signal_log s
     LEFT JOIN LATERAL ( SELECT p.yes_price
           FROM public.price_snapshots p
          WHERE ((p.market_ticker = s.market_ticker) AND (p.ts >= (s.ts - '00:00:30'::interval)) AND (p.ts <= (s.ts + '00:00:30'::interval)))
          ORDER BY (abs(EXTRACT(epoch FROM (p.ts - s.ts))))
         LIMIT 1) p_at ON (true))
     LEFT JOIN LATERAL ( SELECT p.yes_price
           FROM public.price_snapshots p
          WHERE ((p.market_ticker = s.market_ticker) AND (p.ts >= (s.ts + '00:00:50'::interval)) AND (p.ts <= (s.ts + '00:01:10'::interval)))
          ORDER BY p.ts
         LIMIT 1) p_1m ON (true))
     LEFT JOIN LATERAL ( SELECT p.yes_price
           FROM public.price_snapshots p
          WHERE ((p.market_ticker = s.market_ticker) AND (p.ts >= (s.ts + '00:04:30'::interval)) AND (p.ts <= (s.ts + '00:05:30'::interval)))
          ORDER BY p.ts
         LIMIT 1) p_5m ON (true))
     LEFT JOIN LATERAL ( SELECT p.yes_price
           FROM public.price_snapshots p
          WHERE ((p.market_ticker = s.market_ticker) AND (p.ts >= (s.ts + '00:14:00'::interval)) AND (p.ts <= (s.ts + '00:16:00'::interval)))
          ORDER BY p.ts
         LIMIT 1) p_15m ON (true))
     LEFT JOIN LATERAL ( SELECT p.yes_price
           FROM public.price_snapshots p
          WHERE ((p.market_ticker = s.market_ticker) AND (p.ts >= (s.ts + '00:55:00'::interval)) AND (p.ts <= (s.ts + '01:05:00'::interval)))
          ORDER BY p.ts
         LIMIT 1) p_60m ON (true))
  WHERE (s.direction <> 'neutral'::text)
  WITH NO DATA;


ALTER MATERIALIZED VIEW public.signal_outcomes OWNER TO theokelly;

--
-- Name: _hyper_10_30_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_10_30_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_1_25_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_25_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_2_26_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_2_26_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_3_28_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_3_28_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_4_24_chunk is_own_order; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_4_24_chunk ALTER COLUMN is_own_order SET DEFAULT false;


--
-- Name: _hyper_4_24_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_4_24_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_5_10_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_10_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_5_11_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_11_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_5_14_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_14_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_5_15_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_15_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_5_16_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_16_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_5_21_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_21_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_5_31_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_31_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_5_32_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_32_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_5_33_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_33_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_5_34_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_34_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_5_35_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_35_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_5_36_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_36_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_5_37_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_37_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_5_38_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_38_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_5_39_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_39_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_5_40_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_40_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_5_41_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_41_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_5_9_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_5_9_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_6_29_chunk ts; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_6_29_chunk ALTER COLUMN ts SET DEFAULT now();


--
-- Name: _hyper_6_2_chunk ts; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_6_2_chunk ALTER COLUMN ts SET DEFAULT now();


--
-- Name: _hyper_7_22_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_7_22_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_8_27_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_8_27_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_8_7_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_8_7_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_9_23_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_9_23_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: _hyper_9_5_chunk received_at; Type: DEFAULT; Schema: _timescaledb_internal; Owner: theokelly
--

ALTER TABLE ONLY _timescaledb_internal._hyper_9_5_chunk ALTER COLUMN received_at SET DEFAULT now();


--
-- Name: events events_pkey; Type: CONSTRAINT; Schema: public; Owner: theokelly
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (ticker);


--
-- Name: markets markets_pkey; Type: CONSTRAINT; Schema: public; Owner: theokelly
--

ALTER TABLE ONLY public.markets
    ADD CONSTRAINT markets_pkey PRIMARY KEY (ticker);


--
-- Name: series series_pkey; Type: CONSTRAINT; Schema: public; Owner: theokelly
--

ALTER TABLE ONLY public.series
    ADD CONSTRAINT series_pkey PRIMARY KEY (ticker);


--
-- Name: _hyper_10_30_chunk_idx_price_snap_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_10_30_chunk_idx_price_snap_market ON _timescaledb_internal._hyper_10_30_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_10_30_chunk_price_snapshots_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_10_30_chunk_price_snapshots_ts_idx ON _timescaledb_internal._hyper_10_30_chunk USING btree (ts DESC);


--
-- Name: _hyper_1_25_chunk_idx_trades_id; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_1_25_chunk_idx_trades_id ON _timescaledb_internal._hyper_1_25_chunk USING btree (trade_id);


--
-- Name: _hyper_1_25_chunk_idx_trades_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_1_25_chunk_idx_trades_market ON _timescaledb_internal._hyper_1_25_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_1_25_chunk_trades_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_1_25_chunk_trades_ts_idx ON _timescaledb_internal._hyper_1_25_chunk USING btree (ts DESC);


--
-- Name: _hyper_2_26_chunk_idx_ticker_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_2_26_chunk_idx_ticker_market ON _timescaledb_internal._hyper_2_26_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_2_26_chunk_ticker_updates_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_2_26_chunk_ticker_updates_ts_idx ON _timescaledb_internal._hyper_2_26_chunk USING btree (ts DESC);


--
-- Name: _hyper_3_28_chunk_idx_ob_snap_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_3_28_chunk_idx_ob_snap_market ON _timescaledb_internal._hyper_3_28_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_3_28_chunk_orderbook_snapshots_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_3_28_chunk_orderbook_snapshots_ts_idx ON _timescaledb_internal._hyper_3_28_chunk USING btree (ts DESC);


--
-- Name: _hyper_4_24_chunk_idx_ob_delta_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_4_24_chunk_idx_ob_delta_market ON _timescaledb_internal._hyper_4_24_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_4_24_chunk_orderbook_deltas_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_4_24_chunk_orderbook_deltas_ts_idx ON _timescaledb_internal._hyper_4_24_chunk USING btree (ts DESC);


--
-- Name: _hyper_5_10_chunk_idx_lifecycle_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_10_chunk_idx_lifecycle_market ON _timescaledb_internal._hyper_5_10_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_5_10_chunk_lifecycle_events_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_10_chunk_lifecycle_events_ts_idx ON _timescaledb_internal._hyper_5_10_chunk USING btree (ts DESC);


--
-- Name: _hyper_5_11_chunk_idx_lifecycle_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_11_chunk_idx_lifecycle_market ON _timescaledb_internal._hyper_5_11_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_5_11_chunk_lifecycle_events_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_11_chunk_lifecycle_events_ts_idx ON _timescaledb_internal._hyper_5_11_chunk USING btree (ts DESC);


--
-- Name: _hyper_5_14_chunk_idx_lifecycle_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_14_chunk_idx_lifecycle_market ON _timescaledb_internal._hyper_5_14_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_5_14_chunk_lifecycle_events_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_14_chunk_lifecycle_events_ts_idx ON _timescaledb_internal._hyper_5_14_chunk USING btree (ts DESC);


--
-- Name: _hyper_5_15_chunk_idx_lifecycle_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_15_chunk_idx_lifecycle_market ON _timescaledb_internal._hyper_5_15_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_5_15_chunk_lifecycle_events_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_15_chunk_lifecycle_events_ts_idx ON _timescaledb_internal._hyper_5_15_chunk USING btree (ts DESC);


--
-- Name: _hyper_5_16_chunk_idx_lifecycle_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_16_chunk_idx_lifecycle_market ON _timescaledb_internal._hyper_5_16_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_5_16_chunk_lifecycle_events_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_16_chunk_lifecycle_events_ts_idx ON _timescaledb_internal._hyper_5_16_chunk USING btree (ts DESC);


--
-- Name: _hyper_5_21_chunk_idx_lifecycle_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_21_chunk_idx_lifecycle_market ON _timescaledb_internal._hyper_5_21_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_5_21_chunk_lifecycle_events_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_21_chunk_lifecycle_events_ts_idx ON _timescaledb_internal._hyper_5_21_chunk USING btree (ts DESC);


--
-- Name: _hyper_5_31_chunk_idx_lifecycle_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_31_chunk_idx_lifecycle_market ON _timescaledb_internal._hyper_5_31_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_5_31_chunk_lifecycle_events_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_31_chunk_lifecycle_events_ts_idx ON _timescaledb_internal._hyper_5_31_chunk USING btree (ts DESC);


--
-- Name: _hyper_5_32_chunk_idx_lifecycle_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_32_chunk_idx_lifecycle_market ON _timescaledb_internal._hyper_5_32_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_5_32_chunk_lifecycle_events_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_32_chunk_lifecycle_events_ts_idx ON _timescaledb_internal._hyper_5_32_chunk USING btree (ts DESC);


--
-- Name: _hyper_5_33_chunk_idx_lifecycle_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_33_chunk_idx_lifecycle_market ON _timescaledb_internal._hyper_5_33_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_5_33_chunk_lifecycle_events_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_33_chunk_lifecycle_events_ts_idx ON _timescaledb_internal._hyper_5_33_chunk USING btree (ts DESC);


--
-- Name: _hyper_5_34_chunk_idx_lifecycle_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_34_chunk_idx_lifecycle_market ON _timescaledb_internal._hyper_5_34_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_5_34_chunk_lifecycle_events_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_34_chunk_lifecycle_events_ts_idx ON _timescaledb_internal._hyper_5_34_chunk USING btree (ts DESC);


--
-- Name: _hyper_5_35_chunk_idx_lifecycle_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_35_chunk_idx_lifecycle_market ON _timescaledb_internal._hyper_5_35_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_5_35_chunk_lifecycle_events_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_35_chunk_lifecycle_events_ts_idx ON _timescaledb_internal._hyper_5_35_chunk USING btree (ts DESC);


--
-- Name: _hyper_5_36_chunk_idx_lifecycle_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_36_chunk_idx_lifecycle_market ON _timescaledb_internal._hyper_5_36_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_5_36_chunk_lifecycle_events_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_36_chunk_lifecycle_events_ts_idx ON _timescaledb_internal._hyper_5_36_chunk USING btree (ts DESC);


--
-- Name: _hyper_5_37_chunk_idx_lifecycle_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_37_chunk_idx_lifecycle_market ON _timescaledb_internal._hyper_5_37_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_5_37_chunk_lifecycle_events_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_37_chunk_lifecycle_events_ts_idx ON _timescaledb_internal._hyper_5_37_chunk USING btree (ts DESC);


--
-- Name: _hyper_5_38_chunk_idx_lifecycle_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_38_chunk_idx_lifecycle_market ON _timescaledb_internal._hyper_5_38_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_5_38_chunk_lifecycle_events_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_38_chunk_lifecycle_events_ts_idx ON _timescaledb_internal._hyper_5_38_chunk USING btree (ts DESC);


--
-- Name: _hyper_5_39_chunk_idx_lifecycle_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_39_chunk_idx_lifecycle_market ON _timescaledb_internal._hyper_5_39_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_5_39_chunk_lifecycle_events_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_39_chunk_lifecycle_events_ts_idx ON _timescaledb_internal._hyper_5_39_chunk USING btree (ts DESC);


--
-- Name: _hyper_5_40_chunk_idx_lifecycle_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_40_chunk_idx_lifecycle_market ON _timescaledb_internal._hyper_5_40_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_5_40_chunk_lifecycle_events_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_40_chunk_lifecycle_events_ts_idx ON _timescaledb_internal._hyper_5_40_chunk USING btree (ts DESC);


--
-- Name: _hyper_5_41_chunk_idx_lifecycle_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_41_chunk_idx_lifecycle_market ON _timescaledb_internal._hyper_5_41_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_5_41_chunk_lifecycle_events_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_41_chunk_lifecycle_events_ts_idx ON _timescaledb_internal._hyper_5_41_chunk USING btree (ts DESC);


--
-- Name: _hyper_5_9_chunk_idx_lifecycle_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_9_chunk_idx_lifecycle_market ON _timescaledb_internal._hyper_5_9_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_5_9_chunk_lifecycle_events_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_5_9_chunk_lifecycle_events_ts_idx ON _timescaledb_internal._hyper_5_9_chunk USING btree (ts DESC);


--
-- Name: _hyper_6_29_chunk_system_health_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_6_29_chunk_system_health_ts_idx ON _timescaledb_internal._hyper_6_29_chunk USING btree (ts DESC);


--
-- Name: _hyper_6_2_chunk_system_health_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_6_2_chunk_system_health_ts_idx ON _timescaledb_internal._hyper_6_2_chunk USING btree (ts DESC);


--
-- Name: _hyper_7_22_chunk_idx_signal_direction; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_7_22_chunk_idx_signal_direction ON _timescaledb_internal._hyper_7_22_chunk USING btree (direction, ts DESC);


--
-- Name: _hyper_7_22_chunk_idx_signal_log_id; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE UNIQUE INDEX _hyper_7_22_chunk_idx_signal_log_id ON _timescaledb_internal._hyper_7_22_chunk USING btree (signal_id, ts);


--
-- Name: _hyper_7_22_chunk_idx_signal_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_7_22_chunk_idx_signal_market ON _timescaledb_internal._hyper_7_22_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_7_22_chunk_idx_signal_strength; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_7_22_chunk_idx_signal_strength ON _timescaledb_internal._hyper_7_22_chunk USING btree (strength DESC, ts DESC);


--
-- Name: _hyper_7_22_chunk_idx_signal_type; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_7_22_chunk_idx_signal_type ON _timescaledb_internal._hyper_7_22_chunk USING btree (signal_type, ts DESC);


--
-- Name: _hyper_7_22_chunk_signal_log_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_7_22_chunk_signal_log_ts_idx ON _timescaledb_internal._hyper_7_22_chunk USING btree (ts DESC);


--
-- Name: _hyper_8_27_chunk_composite_log_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_8_27_chunk_composite_log_ts_idx ON _timescaledb_internal._hyper_8_27_chunk USING btree (ts DESC);


--
-- Name: _hyper_8_27_chunk_idx_composite_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_8_27_chunk_idx_composite_market ON _timescaledb_internal._hyper_8_27_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_8_27_chunk_idx_composite_regime; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_8_27_chunk_idx_composite_regime ON _timescaledb_internal._hyper_8_27_chunk USING btree (regime, ts DESC);


--
-- Name: _hyper_8_27_chunk_idx_composite_score; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_8_27_chunk_idx_composite_score ON _timescaledb_internal._hyper_8_27_chunk USING btree (composite_score DESC, ts DESC);


--
-- Name: _hyper_8_7_chunk_composite_log_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_8_7_chunk_composite_log_ts_idx ON _timescaledb_internal._hyper_8_7_chunk USING btree (ts DESC);


--
-- Name: _hyper_8_7_chunk_idx_composite_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_8_7_chunk_idx_composite_market ON _timescaledb_internal._hyper_8_7_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_8_7_chunk_idx_composite_regime; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_8_7_chunk_idx_composite_regime ON _timescaledb_internal._hyper_8_7_chunk USING btree (regime, ts DESC);


--
-- Name: _hyper_8_7_chunk_idx_composite_score; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_8_7_chunk_idx_composite_score ON _timescaledb_internal._hyper_8_7_chunk USING btree (composite_score DESC, ts DESC);


--
-- Name: _hyper_9_23_chunk_idx_regime_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_9_23_chunk_idx_regime_market ON _timescaledb_internal._hyper_9_23_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_9_23_chunk_regime_log_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_9_23_chunk_regime_log_ts_idx ON _timescaledb_internal._hyper_9_23_chunk USING btree (ts DESC);


--
-- Name: _hyper_9_5_chunk_idx_regime_market; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_9_5_chunk_idx_regime_market ON _timescaledb_internal._hyper_9_5_chunk USING btree (market_ticker, ts DESC);


--
-- Name: _hyper_9_5_chunk_regime_log_ts_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: theokelly
--

CREATE INDEX _hyper_9_5_chunk_regime_log_ts_idx ON _timescaledb_internal._hyper_9_5_chunk USING btree (ts DESC);


--
-- Name: composite_log_ts_idx; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX composite_log_ts_idx ON public.composite_log USING btree (ts DESC);


--
-- Name: idx_composite_market; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX idx_composite_market ON public.composite_log USING btree (market_ticker, ts DESC);


--
-- Name: idx_composite_regime; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX idx_composite_regime ON public.composite_log USING btree (regime, ts DESC);


--
-- Name: idx_composite_score; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX idx_composite_score ON public.composite_log USING btree (composite_score DESC, ts DESC);


--
-- Name: idx_events_series; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX idx_events_series ON public.events USING btree (series_ticker);


--
-- Name: idx_lifecycle_market; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX idx_lifecycle_market ON public.lifecycle_events USING btree (market_ticker, ts DESC);


--
-- Name: idx_markets_event; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX idx_markets_event ON public.markets USING btree (event_ticker);


--
-- Name: idx_markets_series; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX idx_markets_series ON public.markets USING btree (series_ticker);


--
-- Name: idx_markets_status; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX idx_markets_status ON public.markets USING btree (status);


--
-- Name: idx_ob_delta_market; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX idx_ob_delta_market ON public.orderbook_deltas USING btree (market_ticker, ts DESC);


--
-- Name: idx_ob_snap_market; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX idx_ob_snap_market ON public.orderbook_snapshots USING btree (market_ticker, ts DESC);


--
-- Name: idx_price_snap_market; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX idx_price_snap_market ON public.price_snapshots USING btree (market_ticker, ts DESC);


--
-- Name: idx_regime_market; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX idx_regime_market ON public.regime_log USING btree (market_ticker, ts DESC);


--
-- Name: idx_signal_direction; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX idx_signal_direction ON public.signal_log USING btree (direction, ts DESC);


--
-- Name: idx_signal_log_id; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE UNIQUE INDEX idx_signal_log_id ON public.signal_log USING btree (signal_id, ts);


--
-- Name: idx_signal_market; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX idx_signal_market ON public.signal_log USING btree (market_ticker, ts DESC);


--
-- Name: idx_signal_outcomes_id; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE UNIQUE INDEX idx_signal_outcomes_id ON public.signal_outcomes USING btree (signal_id);


--
-- Name: idx_signal_strength; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX idx_signal_strength ON public.signal_log USING btree (strength DESC, ts DESC);


--
-- Name: idx_signal_type; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX idx_signal_type ON public.signal_log USING btree (signal_type, ts DESC);


--
-- Name: idx_ticker_market; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX idx_ticker_market ON public.ticker_updates USING btree (market_ticker, ts DESC);


--
-- Name: idx_trades_id; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX idx_trades_id ON public.trades USING btree (trade_id);


--
-- Name: idx_trades_market; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX idx_trades_market ON public.trades USING btree (market_ticker, ts DESC);


--
-- Name: lifecycle_events_ts_idx; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX lifecycle_events_ts_idx ON public.lifecycle_events USING btree (ts DESC);


--
-- Name: orderbook_deltas_ts_idx; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX orderbook_deltas_ts_idx ON public.orderbook_deltas USING btree (ts DESC);


--
-- Name: orderbook_snapshots_ts_idx; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX orderbook_snapshots_ts_idx ON public.orderbook_snapshots USING btree (ts DESC);


--
-- Name: price_snapshots_ts_idx; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX price_snapshots_ts_idx ON public.price_snapshots USING btree (ts DESC);


--
-- Name: regime_log_ts_idx; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX regime_log_ts_idx ON public.regime_log USING btree (ts DESC);


--
-- Name: signal_log_ts_idx; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX signal_log_ts_idx ON public.signal_log USING btree (ts DESC);


--
-- Name: system_health_ts_idx; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX system_health_ts_idx ON public.system_health USING btree (ts DESC);


--
-- Name: ticker_updates_ts_idx; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX ticker_updates_ts_idx ON public.ticker_updates USING btree (ts DESC);


--
-- Name: trades_ts_idx; Type: INDEX; Schema: public; Owner: theokelly
--

CREATE INDEX trades_ts_idx ON public.trades USING btree (ts DESC);


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

GRANT USAGE ON SCHEMA public TO kalshi;


--
-- Name: TABLE _compressed_hypertable_11; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._compressed_hypertable_11 TO kalshi;


--
-- Name: TABLE _compressed_hypertable_12; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._compressed_hypertable_12 TO kalshi;


--
-- Name: TABLE _compressed_hypertable_13; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._compressed_hypertable_13 TO kalshi;


--
-- Name: TABLE _compressed_hypertable_14; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._compressed_hypertable_14 TO kalshi;


--
-- Name: TABLE _compressed_hypertable_15; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._compressed_hypertable_15 TO kalshi;


--
-- Name: TABLE _compressed_hypertable_16; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._compressed_hypertable_16 TO kalshi;


--
-- Name: TABLE price_snapshots; Type: ACL; Schema: public; Owner: theokelly
--

GRANT ALL ON TABLE public.price_snapshots TO kalshi;


--
-- Name: TABLE _hyper_10_30_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_10_30_chunk TO kalshi;


--
-- Name: TABLE trades; Type: ACL; Schema: public; Owner: theokelly
--

GRANT ALL ON TABLE public.trades TO kalshi;


--
-- Name: TABLE _hyper_1_25_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_1_25_chunk TO kalshi;


--
-- Name: TABLE ticker_updates; Type: ACL; Schema: public; Owner: theokelly
--

GRANT ALL ON TABLE public.ticker_updates TO kalshi;


--
-- Name: TABLE _hyper_2_26_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_2_26_chunk TO kalshi;


--
-- Name: TABLE orderbook_snapshots; Type: ACL; Schema: public; Owner: theokelly
--

GRANT ALL ON TABLE public.orderbook_snapshots TO kalshi;


--
-- Name: TABLE _hyper_3_28_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_3_28_chunk TO kalshi;


--
-- Name: TABLE orderbook_deltas; Type: ACL; Schema: public; Owner: theokelly
--

GRANT ALL ON TABLE public.orderbook_deltas TO kalshi;


--
-- Name: TABLE _hyper_4_24_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_4_24_chunk TO kalshi;


--
-- Name: TABLE lifecycle_events; Type: ACL; Schema: public; Owner: theokelly
--

GRANT ALL ON TABLE public.lifecycle_events TO kalshi;


--
-- Name: TABLE _hyper_5_10_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_5_10_chunk TO kalshi;


--
-- Name: TABLE _hyper_5_11_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_5_11_chunk TO kalshi;


--
-- Name: TABLE _hyper_5_14_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_5_14_chunk TO kalshi;


--
-- Name: TABLE _hyper_5_15_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_5_15_chunk TO kalshi;


--
-- Name: TABLE _hyper_5_16_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_5_16_chunk TO kalshi;


--
-- Name: TABLE _hyper_5_21_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_5_21_chunk TO kalshi;


--
-- Name: TABLE _hyper_5_31_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_5_31_chunk TO kalshi;


--
-- Name: TABLE _hyper_5_32_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_5_32_chunk TO kalshi;


--
-- Name: TABLE _hyper_5_33_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_5_33_chunk TO kalshi;


--
-- Name: TABLE _hyper_5_34_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_5_34_chunk TO kalshi;


--
-- Name: TABLE _hyper_5_35_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_5_35_chunk TO kalshi;


--
-- Name: TABLE _hyper_5_36_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_5_36_chunk TO kalshi;


--
-- Name: TABLE _hyper_5_37_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_5_37_chunk TO kalshi;


--
-- Name: TABLE _hyper_5_38_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_5_38_chunk TO kalshi;


--
-- Name: TABLE _hyper_5_39_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_5_39_chunk TO kalshi;


--
-- Name: TABLE _hyper_5_40_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_5_40_chunk TO kalshi;


--
-- Name: TABLE _hyper_5_41_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_5_41_chunk TO kalshi;


--
-- Name: TABLE _hyper_5_9_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_5_9_chunk TO kalshi;


--
-- Name: TABLE system_health; Type: ACL; Schema: public; Owner: theokelly
--

GRANT ALL ON TABLE public.system_health TO kalshi;


--
-- Name: TABLE _hyper_6_29_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_6_29_chunk TO kalshi;


--
-- Name: TABLE _hyper_6_2_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_6_2_chunk TO kalshi;


--
-- Name: TABLE signal_log; Type: ACL; Schema: public; Owner: theokelly
--

GRANT ALL ON TABLE public.signal_log TO kalshi;


--
-- Name: TABLE _hyper_7_22_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_7_22_chunk TO kalshi;


--
-- Name: TABLE composite_log; Type: ACL; Schema: public; Owner: theokelly
--

GRANT ALL ON TABLE public.composite_log TO kalshi;


--
-- Name: TABLE _hyper_8_27_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_8_27_chunk TO kalshi;


--
-- Name: TABLE _hyper_8_7_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_8_7_chunk TO kalshi;


--
-- Name: TABLE regime_log; Type: ACL; Schema: public; Owner: theokelly
--

GRANT ALL ON TABLE public.regime_log TO kalshi;


--
-- Name: TABLE _hyper_9_23_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_9_23_chunk TO kalshi;


--
-- Name: TABLE _hyper_9_5_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: theokelly
--

GRANT ALL ON TABLE _timescaledb_internal._hyper_9_5_chunk TO kalshi;


--
-- Name: TABLE events; Type: ACL; Schema: public; Owner: theokelly
--

GRANT ALL ON TABLE public.events TO kalshi;


--
-- Name: TABLE hourly_volume; Type: ACL; Schema: public; Owner: theokelly
--

GRANT ALL ON TABLE public.hourly_volume TO kalshi;


--
-- Name: TABLE market_latest; Type: ACL; Schema: public; Owner: theokelly
--

GRANT ALL ON TABLE public.market_latest TO kalshi;


--
-- Name: TABLE markets; Type: ACL; Schema: public; Owner: theokelly
--

GRANT ALL ON TABLE public.markets TO kalshi;


--
-- Name: TABLE oi_by_market; Type: ACL; Schema: public; Owner: theokelly
--

GRANT ALL ON TABLE public.oi_by_market TO kalshi;


--
-- Name: TABLE series; Type: ACL; Schema: public; Owner: theokelly
--

GRANT ALL ON TABLE public.series TO kalshi;


--
-- Name: TABLE signal_outcomes; Type: ACL; Schema: public; Owner: theokelly
--

GRANT ALL ON TABLE public.signal_outcomes TO kalshi;


--
-- PostgreSQL database dump complete
--

\unrestrict 4mPJ0Y7hS1NokgeU3V1CNbNSWiWTnejGekUyujfBnIE4Xbzp43xEBahMgeoEGcj

