"""Central configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class KalshiConfig(BaseSettings):
    api_key_id: str = Field(default="", alias="KALSHI_API_KEY_ID")
    private_key_path: Path = Field(default=Path("keys/kalshi_private_key.pem"), alias="KALSHI_PRIVATE_KEY_PATH")
    api_base_url: str = Field(default="https://api.elections.kalshi.com", alias="KALSHI_API_BASE_URL")
    ws_url: str = Field(
        default="wss://api.elections.kalshi.com/trade-api/ws/v2", alias="KALSHI_WS_URL"
    )


class PostgresConfig(BaseSettings):
    host: str = Field(default="localhost", alias="POSTGRES_HOST")
    port: int = Field(default=5432, alias="POSTGRES_PORT")
    db: str = Field(default="kalshi_alpha", alias="POSTGRES_DB")
    user: str = Field(default="kalshi", alias="POSTGRES_USER")
    password: str = Field(default="", alias="POSTGRES_PASSWORD")
    pool_min: int = Field(default=2, alias="POSTGRES_POOL_MIN")
    pool_max: int = Field(default=10, alias="POSTGRES_POOL_MAX")

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class RedisConfig(BaseSettings):
    host: str = Field(default="localhost", alias="REDIS_HOST")
    port: int = Field(default=6379, alias="REDIS_PORT")
    db: int = Field(default=0, alias="REDIS_DB")
    password: str = Field(default="", alias="REDIS_PASSWORD")

    @property
    def url(self) -> str:
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class MonitoringConfig(BaseSettings):
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")
    health_check_interval: int = Field(default=30, alias="HEALTH_CHECK_INTERVAL")
    alert_cooldown: int = Field(default=300, alias="ALERT_COOLDOWN")


class TuningConfig(BaseSettings):
    trade_writer_batch_size: int = Field(default=100, alias="TRADE_WRITER_BATCH_SIZE")
    trade_writer_flush_interval: float = Field(default=5.0, alias="TRADE_WRITER_FLUSH_INTERVAL")
    orderbook_snapshot_interval: int = Field(default=60, alias="ORDERBOOK_SNAPSHOT_INTERVAL")
    market_scan_interval: int = Field(default=300, alias="MARKET_SCAN_INTERVAL")
    ws_ping_interval: int = Field(default=30, alias="WS_PING_INTERVAL")
    ws_pong_timeout: int = Field(default=10, alias="WS_PONG_TIMEOUT")
    ws_reconnect_max_delay: int = Field(default=60, alias="WS_RECONNECT_MAX_DELAY")


class LoggingConfig(BaseSettings):
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")


class AppConfig:
    """Aggregated application configuration."""

    def __init__(self) -> None:
        self.kalshi = KalshiConfig()
        self.postgres = PostgresConfig()
        self.redis = RedisConfig()
        self.monitoring = MonitoringConfig()
        self.tuning = TuningConfig()
        self.logging = LoggingConfig()


def get_config() -> AppConfig:
    """Create and return the application configuration."""
    return AppConfig()
