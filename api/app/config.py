"""Application settings.

Only infrastructure settings live here (database URL, JWT settings, LLM keys).
Procurement thresholds, limits and percentages are NEVER stored here - they
live in the procurement_rules table and are read through the rules service.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root, i.e. the directory that holds .env
ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Later files win in pydantic-settings, so .env must come last.
        env_file=(ROOT_DIR / ".env.example", ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/procureflow"
    db_name: str = "procureflow"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720

    demo_password: str = "demo1234"

    cors_origins: str = (
        "http://localhost:5173,http://localhost:5174,http://localhost:5175,http://localhost:5176,"
        "http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:5175,http://127.0.0.1:5176"
    )

    llm_provider: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    embedding_model: str = "all-MiniLM-L6-v2"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
