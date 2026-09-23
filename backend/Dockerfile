# INNOVATE-GOV backend — FastAPI.
#
# Replaces the previous Maven/Temurin image that built the Spring Boot jar.
# The AI pipeline now runs inside this same process (backend/app/ai/), so the
# deployment no longer has a separate AI container to coordinate with.
#
# Build from the repo root:
#   docker compose -f docker/docker-compose.yml build backend

FROM python:3.11-slim

# Fail fast and log straight through to the container's stdout rather than
# buffering, so `docker logs` shows startup problems as they happen.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, as their own layer: application code changes far more
# often than requirements.txt, and torch/sentence-transformers are slow to
# install. Both ship prebuilt manylinux wheels for this Python version, so no
# compiler toolchain is needed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding model at build time. A cold `all-MiniLM-L6-v2`
# load takes ~50s; baking it into the image means the first "Find Suitable
# Startups" request in a running container does not pay for it. This is the
# same technique the old ai-service Dockerfile used, carried over.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY app ./app

# Uploaded documents. Backed by a named volume in docker-compose so they
# survive a container rebuild; FILE_STORAGE_PATH points here.
RUN mkdir -p /uploads

EXPOSE 8000

# Reports unhealthy until PostgreSQL is actually reachable — /health returns
# {"status": "UP"} only when a `SELECT 1` succeeds, so compose's
# `depends_on: condition: service_healthy` becomes meaningful for the frontend.
HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=5 \
    CMD python -c "import urllib.request,sys,json; \
sys.exit(0 if json.load(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4))['status']=='UP' else 1)"

# Uvicorn directly rather than `--reload`: this is the production entrypoint.
# A single worker is deliberate — the embedding model is several hundred MB
# resident, and each worker would load its own copy. Scale with replicas that
# share the database rather than with workers inside one container.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
