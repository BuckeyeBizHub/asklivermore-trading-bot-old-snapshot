"""
core.config
===========
Centralized settings loaded from .env via pydantic-settings.
Import `settings` anywhere; never read os.environ directly.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # mode
    execution_mode: Literal["scan-only", "paper", "live", "replay"] = "paper"
    broker: Literal["alpaca", "ibkr"] = "alpaca"
    log_level: str = "INFO"
    timezone: str = "America/New_York"

    # anthropic
    anthropic_api_key: str = ""
    reasoning_model: str = "claude-opus-4-7"
    utility_model: str = "claude-haiku-4-5-20251001"

    # polygon
    polygon_api_key: str = ""
    polygon_websocket_url: str = "wss://socket.polygon.io/stocks"

    # alpaca
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"

    # ibkr
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497
    ibkr_client_id: int = 42
    ibkr_account: str = ""

    # risk
    max_risk_pct: float = 0.02
    max_daily_loss_pct: float = 0.03
    max_drawdown_pct: float = 0.08
    max_open_positions: int = 5
    heartbeat_timeout_s: int = 120

    # confluence
    min_confluence_score: int = 4
    min_sentiment_score: float = 0.0

    # graphify
    graphify_url: str = "http://graphify:7000"
    graphify_api_key: str = ""
    graphify_namespace: str = "asklivermore"

    # enrichment
    marketaux_api_key: str = ""
    styvio_api_key: str = ""

    # notifications
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    sms_provider: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from: str = ""
    sms_to: str = ""

    # external repos
    external_path_graphify: Path = Path("./external/graphify")
    external_path_social_skills: Path = Path("./external/social-media-skills")
    external_path_claude_peers: Path = Path("./external/claude-peers")

    # csv
    csv_import_dir: Path = Path("./data/csv_imports")
    csv_schema_path: Path = Path("./core/csv_schema.yaml")

    # peers
    peer_id: str = "primary"
    peer_topic: str = "asklivermore-trading"

    # data dirs
    data_dir: Path = Field(default=Path("./data"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
