"""ProcureFlow API.

All AI work (embeddings, the problem analyzer, matching) runs in-process inside
this FastAPI app - there is no separate AI service to start.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import admin, auth, challenges, engine, pilots, proposals

app = FastAPI(
    title="ProcureFlow API",
    description=(
        "Startup-friendly public procurement platform - prototype for "
        "Smart India Hackathon 2026, problem statement SIH26136."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(engine.router)
app.include_router(challenges.router)
app.include_router(proposals.router)
app.include_router(pilots.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "service": "procureflow-api"}


@app.get("/ai-status", tags=["meta"])
def ai_status() -> dict:
    """What the AI layer can actually do right now.

    The demo is meant to run offline, so it says plainly whether it is using a
    provider or the deterministic fallback, rather than pretending either way.
    """
    from app.services import embeddings, llm

    return {"llm": llm.describe(), "embeddings": embeddings.status().as_dict()}
