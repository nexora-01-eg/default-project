"""Application configuration.

Layered, environment-driven settings. Every knob the spec requires to be
configurable (retention, concurrency, rate limits, providers, ports) lives
here and is overridable through `.env` or real environment variables.

Secrets are never hard-coded, never logged (`redacted()`), and never returned
by the API (Phase 17).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # .../apps/ai-service-demand-radar
BACKEND_DIR = PROJECT_ROOT / "backend"
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
DOCS_DIR = PROJECT_ROOT / "docs"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
EXPORT_DIR = DATA_DIR / "exports"

SECRET_MARKERS = ("key", "token", "secret", "password", "credential")


class Settings(BaseSettings):
    """Runtime configuration for the whole application."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # app
    app_name: str = "AI Service Demand Radar"
    app_env: str = "local"
    debug: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # storage
    database_url: str = ""

    # outbound http
    http_timeout_seconds: float = 20.0
    http_max_retries: int = 3
    http_backoff_seconds: float = 1.5
    user_agent: str = (
        "AIServiceDemandRadar/1.0 (local research tool; respectful crawler; "
        "set RADAR_CONTACT_EMAIL to advertise a contact)"
    )
    contact_email: str = ""
    respect_robots_txt: bool = True

    # scan orchestration
    scan_max_concurrency: int = 2
    scan_job_timeout_seconds: int = 600
    scan_retry_max: int = 3
    scheduler_enabled: bool = True
    scheduler_poll_seconds: int = 20

    # per-source rate limits (requests per minute)
    rate_limit_default_per_minute: int = 10
    rate_limit_reddit_per_minute: int = 10
    rate_limit_rss_per_minute: int = 30
    rate_limit_web_per_minute: int = 6

    # AI provider
    ai_provider: str = "auto"  # auto | heuristic | ollama | openai_compatible
    ai_model: str = ""
    ai_base_url: str = "http://localhost:11434"
    ai_api_key: str = ""
    ai_timeout_seconds: float = 120.0
    ai_max_candidates_per_scan: int = 60
    ai_temperature: float = 0.0

    # alerts
    alert_min_intent_score: int = 85
    alert_webhook_url: str = ""
    alert_email_to: str = ""
    alert_channels: str = "dashboard"

    # retention (days; 0 = keep forever)
    raw_result_retention_days: int = 30
    log_retention_days: int = 14
    lead_retention_days: int = 0

    # optional source credentials
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = ""
    youtube_api_key: str = ""
    github_token: str = ""

    # discovery defaults
    default_sources: str = "hackernews,rss,reddit_public,web_search,job_boards"
    max_results_per_query: int = 25

    @field_validator("scan_max_concurrency", "scan_retry_max", "http_max_retries")
    @classmethod
    def _at_least_one(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be >= 1")
        return value

    @field_validator("ai_temperature")
    @classmethod
    def _temperature_range(cls, value: float) -> float:
        if not 0.0 <= value <= 2.0:
            raise ValueError("ai_temperature must be between 0.0 and 2.0")
        return value

    @field_validator("ai_provider")
    @classmethod
    def _known_provider(cls, value: str) -> str:
        allowed = {"auto", "heuristic", "ollama", "openai_compatible"}
        lowered = (value or "auto").strip().lower()
        if lowered not in allowed:
            raise ValueError(f"ai_provider must be one of {sorted(allowed)}")
        return lowered

    # ------------------------------------------------------------- helpers
    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def alert_channel_list(self) -> list[str]:
        return [item.strip().lower() for item in self.alert_channels.split(",") if item.strip()]

    @property
    def default_source_list(self) -> list[str]:
        return [item.strip() for item in self.default_sources.split(",") if item.strip()]

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return "sqlite:///" + (DATA_DIR / "radar.db").as_posix()

    def rate_limit_for_source(self, name: str) -> int:
        return {
            "default": self.rate_limit_default_per_minute,
            "reddit_public": self.rate_limit_reddit_per_minute,
            "rss": self.rate_limit_rss_per_minute,
            "web_search": self.rate_limit_web_per_minute,
        }.get(name, self.rate_limit_default_per_minute)

    def ensure_dirs(self) -> None:
        for directory in (DATA_DIR, LOGS_DIR, EXPORT_DIR):
            directory.mkdir(parents=True, exist_ok=True)

    def redacted(self) -> dict[str, object]:
        """Settings dump with every secret replaced by a status marker."""
        out: dict[str, object] = {}
        for name, value in self.model_dump().items():
            if any(marker in name.lower() for marker in SECRET_MARKERS):
                out[name] = "__SET__" if value else ""
            else:
                out[name] = value
        return out

    def has_ai_credentials(self) -> bool:
        """True only when the configured provider can actually be called."""
        provider = (self.ai_provider or "auto").lower()
        if provider == "heuristic":
            return False
        if provider == "ollama":
            return bool(self.ai_base_url)
        if provider == "openai_compatible":
            return bool(self.ai_base_url and self.ai_api_key)
        return bool(self.ai_api_key and self.ai_base_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings


def reload_settings() -> Settings:
    """Force a re-read of the environment (used by tests and the CLI)."""
    get_settings.cache_clear()
    return get_settings()


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}