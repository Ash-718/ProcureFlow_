import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.embeddings import get_embedding_provider
from app.core.text_generation import get_text_generation_provider
from app.routers import health, matching

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ai-service")

settings = get_settings()

app = FastAPI(
    title="INNOVATE-GOV AI Service",
    description="Embeddings, weighted matching, explanations and knowledge-base search for SIH26136.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_allowed_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "AI_SERVICE_ERROR", "message": str(exc), "path": str(request.url.path)},
    )


app.include_router(health.router)
app.include_router(matching.router)


@app.on_event("startup")
def warm_up_providers():
    # Load the embedding model (and validate the text-gen provider) once at startup
    # rather than on the first request, so the first "Find Suitable Startups" click
    # during a demo isn't the moment the ~15-20s model load happens.
    provider = get_embedding_provider()
    text_provider = get_text_generation_provider()
    logger.info(
        "AI service ready. embedding_provider=%s text_generation_provider=%s",
        provider.name,
        text_provider.name,
    )
