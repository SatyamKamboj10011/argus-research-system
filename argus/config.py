"""Application configuration, loaded from the environment.

Every tunable lives here so that nothing else in the codebase reads ``os.environ``
directly. Values are validated at import time, which means a misconfigured
deployment fails fast at boot instead of halfway through a user's research run.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Provider credentials ────────────────────────────────────────────────
    tavily_api_key: str | None = None
    groq_api_key: str | None = None
    cerebras_api_key: str | None = None
    google_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    # ── HTTP surface ────────────────────────────────────────────────────────
    allowed_origins: str = "*"
    """Comma-separated list of allowed CORS origins. ``*`` only for local dev."""

    # ── Limits ──────────────────────────────────────────────────────────────
    max_topic_length: int = Field(default=300, ge=10, le=2000)
    min_topic_length: int = Field(default=3, ge=1)
    pipeline_timeout_seconds: int = Field(default=280, ge=30, le=3600)
    search_max_results: int = Field(default=6, ge=1, le=20)
    scrape_max_pages: int = Field(default=3, ge=1, le=10)
    scrape_timeout_seconds: float = Field(default=8.0, gt=0)
    scrape_max_bytes: int = Field(default=2_000_000, ge=10_000)
    scrape_max_chars: int = Field(default=6_000, ge=500)
    max_research_chars: int = Field(default=14_000, ge=1_000)
    """Cap on the research blob handed to a single chain.

    Free inference tiers meter tokens per minute, so an unbounded payload does not
    merely cost more - it fails outright with a 413."""

    review_concurrency: int = Field(default=2, ge=1, le=8)
    """How many review chains may be in flight at once. Kept low so a free-tier
    token-per-minute budget is not exhausted by fan-out."""

    llm_max_retries: int = Field(default=3, ge=0, le=6)

    # ── Rate limiting (per client IP) ───────────────────────────────────────
    rate_limit_requests: int = Field(default=10, ge=1)
    rate_limit_window_seconds: int = Field(default=600, ge=1)

    # ── Caching ─────────────────────────────────────────────────────────────
    cache_enabled: bool = True
    cache_ttl_seconds: int = Field(default=1800, ge=0)
    cache_max_entries: int = Field(default=64, ge=1)

    # ── Behaviour ───────────────────────────────────────────────────────────
    allow_local_models: bool = False
    """Ollama-backed models are only offered when the server can reach Ollama."""

    log_level: str = "INFO"

    @field_validator("log_level")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()


settings = get_settings()
