"""
Application settings.

Reads the *same environment variable names* the Spring backend used, so an
existing `backend/.env` keeps working through the migration and nobody has to
maintain two parallel config files while both backends coexist.

The one wrinkle is `DATABASE_URL`: Spring stores a JDBC URL
(`jdbc:postgresql://host:port/db`) which SQLAlchemy cannot parse. Rather than
force a second variable, `normalise_database_url` translates JDBC form into a
SQLAlchemy URL and folds in the separate user/password variables that JDBC
keeps outside the URL string.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = BACKEND_ROOT.parent

_JDBC_RE = re.compile(r"^jdbc:postgresql://(?P<host>[^:/]+)(?::(?P<port>\d+))?/(?P<db>[^?]+)")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        extra="ignore",
        case_sensitive=False,
    )

    # --- database --------------------------------------------------------
    # Default matches the AI service's existing default: local PostgreSQL 17
    # on 5433, role `innovategov`, no password.
    database_url: str = "postgresql+psycopg://innovategov:@127.0.0.1:5433/innovategov"
    database_user: str = ""
    database_password: str = ""
    db_echo: bool = False

    # --- auth ------------------------------------------------------------
    jwt_secret: str = "dev-only-insecure-secret-change-me-please-1234567890"
    # Milliseconds, matching Spring's `app.jwt.expiry-ms` (24 h).
    jwt_expiry_ms: int = 86_400_000
    # NOTE: there is deliberately no `jwt_algorithm` setting. jjwt derives the
    # HMAC algorithm from the secret's length, and `app.security.jwt` reproduces
    # that rule so tokens stay interchangeable with the Spring backend. A
    # configurable value here would be silently ignored.

    # --- CORS ------------------------------------------------------------
    # Comma-separated, same convention as the Spring SecurityConfig.
    cors_allowed_origin: str = (
        "http://localhost:5173,http://localhost:5174,"
        "http://localhost:5175,http://localhost:5176"
    )

    # --- files -----------------------------------------------------------
    file_storage_path: str = str(REPO_ROOT / "uploads")

    # --- server ----------------------------------------------------------
    server_port: int = 8000

    # --- rate limiting (port of RateLimitFilter) -------------------------
    # Values match RateLimitFilter exactly: 15 requests per 60s, per client IP,
    # applied only to /api/v1/auth/.
    rate_limit_requests: int = 15
    rate_limit_window_seconds: int = 60

    # --- AI (migrated from ai-service settings) -------------------------
    embedding_provider: str = "local"
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_dimensions: int = 384

    llm_api_key: str | None = None
    llm_api_base: str = "https://api.openai.com/v1"
    llm_embedding_model: str = "text-embedding-3-small"
    llm_chat_model: str = "gpt-4o-mini"

    # Weighted matching formula. Defaults mirror `ai_matching_config` in
    # database/schema.sql, which stays the documented source of truth.
    weight_semantic_similarity: float = 0.35
    weight_technology_match: float = 0.20
    weight_domain_match: float = 0.15
    weight_experience: float = 0.15
    weight_readiness: float = 0.15

    match_top_n: int = 8

    # Load the sentence-transformers model on a background thread at startup.
    # A cold load takes ~50s, so without this the first "Find Suitable
    # Startups" click of a demo pays for it. The thread is a daemon and never
    # blocks boot; disable it for short-lived processes such as scripts.
    ai_warm_up_on_startup: bool = True

    # -- derived ----------------------------------------------------------

    @property
    def sqlalchemy_url(self) -> str:
        return normalise_database_url(
            self.database_url, self.database_user, self.database_password
        )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origin.split(",") if o.strip()]

    @property
    def jwt_expiry_seconds(self) -> int:
        return self.jwt_expiry_ms // 1000

    @property
    def upload_dir(self) -> Path:
        path = Path(self.file_storage_path)
        if not path.is_absolute():
            path = (BACKEND_ROOT / path).resolve()
        return path

    @property
    def matching_weights(self) -> dict[str, float]:
        """Weight dict in the exact shape `app.ai.scoring` expects."""
        return {
            "semantic_similarity": self.weight_semantic_similarity,
            "technology_match": self.weight_technology_match,
            "domain_match": self.weight_domain_match,
            "experience_score": self.weight_experience,
            "readiness_score": self.weight_readiness,
        }


def normalise_database_url(url: str, user: str = "", password: str = "") -> str:
    """
    Accept either a SQLAlchemy URL or Spring's JDBC URL and return the former.

    JDBC keeps credentials in separate properties, so when a JDBC URL is given
    the `user`/`password` arguments are folded into the result. Credentials are
    percent-encoded, which matters for passwords containing `@` or `:`.
    """
    if not url.startswith("jdbc:"):
        return url

    match = _JDBC_RE.match(url)
    if not match:
        raise ValueError(f"Unrecognised JDBC URL: {url!r}")

    host = match.group("host")
    port = match.group("port") or "5432"
    database = match.group("db")

    credentials = ""
    if user:
        credentials = quote(user, safe="")
        # A trailing ':' is meaningful — it means "user, empty password", which
        # is exactly how the seeded `innovategov` role is configured.
        credentials += ":" + quote(password, safe="") if password else ":"
        credentials += "@"

    return f"postgresql+psycopg://{credentials}{host}:{port}/{database}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
