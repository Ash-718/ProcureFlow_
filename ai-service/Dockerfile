FROM python:3.11-slim

WORKDIR /app

# Keep pip's wheel cache out of the final layer; torch/sentence-transformers are
# large but ship prebuilt manylinux wheels for this Python version, so no
# compiler toolchain is needed here.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Pre-download the local embedding model at build time so the first real
# request doesn't pay a ~15-20s cold-start cost inside a running container.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

EXPOSE 8081

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081"]
