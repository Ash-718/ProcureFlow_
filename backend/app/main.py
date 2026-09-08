"""
FastAPI application entry point.

**Phase 5 scope.** Foundation, security layer, the auth / challenge / startup
routers, and the AI pipeline now running in-process under `app/ai/`. The
remaining routers (matching, proposals, documents, evaluations, pilots,
knowledge base, notifications, admin) still live on the Spring backend at
:8001, which stays the reference implementation until Phase 10.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import check_connection
from app.core.exceptions import register_exception_handlers
from app.security.rate_limit import RateLimitMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("innovategov")

app = FastAPI(
    title="INNOVATE-GOV API",
    description=(
        "AI-powered innovation procurement platform for the Government of "
        "Maharashtra (SIH26136). Python/FastAPI backend."
    ),
    version="1.0.0",
    docs_url="/swagger-ui",
    openapi_url="/api-docs",
)

# Order matters: the rate limiter is added first so it sits *inside* CORS and
# a 429 still carries CORS headers. Starlette applies middleware in reverse
# registration order, so the last one added is the outermost.
app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

register_exception_handlers(app)


# ---------------------------------------------------------------------------
# Public endpoints (ported from RootController)
# ---------------------------------------------------------------------------

@app.get("/", tags=["system"])
def root() -> dict:
    return {
        "name": "INNOVATE-GOV API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/swagger-ui",
    }


@app.get("/health", tags=["system"])
def health() -> dict:
    database_up = check_connection()
    return {
        "status": "UP" if database_up else "DEGRADED",
        "database": "UP" if database_up else "DOWN",
    }


# ---------------------------------------------------------------------------
# Business routers
# ---------------------------------------------------------------------------

app.include_router(api_router)


# ---------------------------------------------------------------------------

@app.on_event("startup")
def log_startup() -> None:
    # Report the database state once at boot rather than letting the first
    # request be the thing that discovers PostgreSQL is not running.
    from app.security.jwt import secret_bytes, select_algorithm

    if check_connection():
        logger.info("Database reachable at %s", _safe_url())
    else:
        logger.warning(
            "Database NOT reachable at %s — start PostgreSQL before using the API.",
            _safe_url(),
        )
    logger.info(
        "JWT algorithm %s (derived from a %d-byte secret, matching jjwt)",
        select_algorithm(secret_bytes()), len(secret_bytes()),
    )
    if settings.ai_warm_up_on_startup:
        _warm_up_ai_model()


def _warm_up_ai_model() -> None:
    """
    Load the embedding model on a background thread.

    A cold `all-MiniLM-L6-v2` load takes roughly 50 seconds. The standalone AI
    service paid that at startup so the first match of a demo would not; doing
    it on a daemon thread keeps that benefit without delaying boot or blocking
    the first request that does not need the model.
    """
    import threading

    def _load() -> None:
        try:
            from app.ai import get_embedding_provider

            provider = get_embedding_provider()
            logger.info("AI embedding provider ready: %s", provider.name)
        except Exception:  # noqa: BLE001 - never let warm-up break the app
            logger.warning(
                "AI model warm-up failed; it will load on first use.",
                exc_info=True,
            )

    threading.Thread(target=_load, name="ai-warmup", daemon=True).start()
    logger.info("AI embedding model warming up in the background...")


def _safe_url() -> str:
    """Connection URL with any password removed, safe to log."""
    url = settings.sqlalchemy_url
    if "@" in url and "//" in url:
        scheme, rest = url.split("//", 1)
        credentials, host = rest.split("@", 1)
        user = credentials.split(":", 1)[0]
        return f"{scheme}//{user}:***@{host}"
    return url
