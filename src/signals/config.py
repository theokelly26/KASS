"""Signal-specific configuration for all Phase 2 processors."""

from __future__ import annotations

FLOW_TOXICITY_CONFIG = {
    "vpin_threshold": 0.80,
    "rolling_vpin_threshold": 0.70,
    "bucket_size": 25,
    "window_size": 20,
    "burst_window_seconds": 5.0,
    "burst_min_trades": 8,
    "size_multiplier": 3.0,
    "min_market_volume": 200,
}

OI_DIVERGENCE_CONFIG = {
    "min_observations": 30,
    "oi_zscore_threshold": 2.5,
    "window_size": 50,
    "dollar_oi_confirmation_boost": 0.15,
    "min_price_for_signal": 5,
    "max_price_for_signal": 95,
}

REGIME_CONFIG = {
    "publish_interval": 30,
    "dead_trade_rate": 0.2,
    "dead_message_rate": 0.1,
    "informed_imbalance": 0.6,
    "informed_trade_rate": 5,
    "active_trade_rate": 2,
    "pre_settle_price_threshold": 5,
    "pre_settle_trade_rate": 2,
}

CROSS_MARKET_CONFIG = {
    "min_price_move": 3,
    "propagation_window": 30,
    "signal_attenuation": 0.7,
    "confidence_attenuation": 0.6,
    "max_related_markets": 20,
    "min_source_strength": 0.5,
}

LIFECYCLE_CONFIG = {
    "new_market_window": 300,
    "settlement_cascade_window": 120,
}

AGGREGATOR_CONFIG = {
    "min_composite_score": 0.4,
    "cleanup_interval": 60,
    "max_active_signals_per_market": 20,
    "publish_cooldown": 10,
}
