import os
from pydantic_settings import BaseSettings


def _resolve_redis_url() -> str:
    """
    Railway injects Redis connection info under several possible variable names.
    Check them in priority order to find a valid Redis URL.

    Priority:
    1. REDIS_PRIVATE_URL  — Railway internal network (fastest, preferred)
    2. REDIS_URL          — Railway public URL (may be rediss:// TLS)
    3. REDISURL           — Some Railway templates use this
    4. CELERY_BROKER_URL  — Explicit override
    5. Default localhost  — for local dev only
    """
    for var in ("REDIS_PRIVATE_URL", "REDIS_URL", "REDISURL", "CELERY_BROKER_URL"):
        val = os.environ.get(var, "")
        if val and (val.startswith("redis://") or val.startswith("rediss://")):
            return val
    return "redis://localhost:6379/0"


class Settings(BaseSettings):
    # App
    app_env: str = "development"
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "postgresql://evaluser:evalpassword@localhost:5432/evaldb"

    # Redis — can be set via REDIS_URL env var; resolved at startup with fallback chain
    redis_url: str = ""

    # LLM
    llm_provider: str = "gemini"
    llm_model: str = "gemini-1.5-flash"
    llm_mock_mode: bool = False
    gemini_api_key: str = ""
    openai_api_key: str = ""

    # Evaluation thresholds
    latency_threshold_ms: int = 1000
    pattern_scan_window: int = 100
    auto_label_confidence_threshold: float = 0.8
    annotator_agreement_threshold: float = 0.6

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def celery_broker_url(self) -> str:
        """
        Return the Redis URL for Celery broker/backend.
        Handles both redis:// (plain) and rediss:// (TLS) schemes used by Railway.
        """
        # Explicit REDIS_URL from .env or env var takes first priority
        if self.redis_url and (
            self.redis_url.startswith("redis://")
            or self.redis_url.startswith("rediss://")
        ):
            return self.redis_url
        # Use the smart resolver to check all Railway variable names
        return _resolve_redis_url()


settings = Settings()

# Ensure redis_url is always populated (for DB-level consumers like health checks)
if not settings.redis_url:
    # Can't assign to pydantic model field directly after init, so we resolve lazily
    # via celery_broker_url property — both tasks.py and any direct consumer use it
    pass
