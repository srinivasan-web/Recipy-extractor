from functools import lru_cache
from pathlib import Path
import math

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
BACKEND_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
DEFAULT_SQLITE_URL = "sqlite+pysqlite:///:memory:"


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class Settings(BaseSettings):
    app_name: str = "Recipe Extractor & Meal Planner API"
    api_prefix: str = "/api"
    database_url: str = DEFAULT_SQLITE_URL
    database_fallback_enabled: bool = True
    database_fallback_url: str | None = None
    cors_allowed_origins: str = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "http://localhost:5174,"
        "http://127.0.0.1:5174"
    )
    cors_allowed_origin_regex: str = r"https://.*\.vercel\.app"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_fallback_model: str | None = None
    request_timeout_seconds: int = 20
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    llm_max_retries: int = 3
    llm_unavailable_retries: int = 6
    llm_retry_backoff_seconds: float = 1.0
    llm_best_effort_enrichment: bool = True
    scraper_max_retries: int = 3
    scraper_retry_backoff_seconds: float = 1.0
    browser_fallback_enabled: bool = False
    browser_first_enabled: bool = False
    selenium_driver_path: str | None = None

    model_config = SettingsConfigDict(
        env_file=(str(ROOT_ENV_FILE), str(BACKEND_ENV_FILE)),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
