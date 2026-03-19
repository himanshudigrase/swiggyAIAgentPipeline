import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_env: str = "development"
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "postgresql://evaluser:evalpassword@localhost:5432/evaldb"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # LLM
    llm_provider: str = "gemini"           # "gemini" or "openai"
    llm_model: str = "gemini-1.5-flash"
    llm_mock_mode: bool = False            # True = return mock responses, no API key needed
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


settings = Settings()
