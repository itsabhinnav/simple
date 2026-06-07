# =============================================================================
# Sakura backend - standalone image (API only, no Angular SPA).
#
# Prefer the repo-root `Dockerfile.unified` (driven by `docker-compose.yml`)
# for production. This file is kept for environments that already have the
# Angular SPA hosted elsewhere (CDN, separate Nginx) and only need the API.
# =============================================================================
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    FLASK_ENV=production \
    HOST=0.0.0.0 \
    PORT=5000 \
    ENABLE_NETWORK_RESTRICTIONS=strict \
    FORCE_HTTPS=false \
    SAKURA_LLM_ALLOW_EXTERNAL=false \
    SAKURA_LLM_ALLOW_REMOTE_OLLAMA=false \
    SAKURA_DISABLE_OLLAMA_SIDECAR=true \
    SAKURA_DISABLE_LIVE_INDEXER=false \
    OLLAMA_MODELS=/app/data/ollama/models \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=5

WORKDIR /app

# Runtime deps (see Dockerfile.unified for a fuller annotation):
#   * git, curl, ca-certificates           - infra basics + healthcheck
#   * libreoffice-core/calc/writer         - hybrid parser visual preprocessor
#   * poppler-utils, fonts-dejavu-core     - pdf -> png + glyph rendering
# psycopg2-binary ships manylinux wheels for amd64/arm64, so libpq-dev is
# no longer required in the image.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        git curl ca-certificates \
        libreoffice-core libreoffice-calc libreoffice-writer \
        poppler-utils fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt

COPY . .

# Local-only persistence layout (no more data/remote/* — Git sync was removed).
RUN mkdir -p data/local/dev/database data/local/dev/vectors \
             data/ollama/models uploads/specs

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail --silent --show-error \
        "http://127.0.0.1:${PORT:-5000}/health" || exit 1

# run_server.py picks the right WSGI server per-platform (Gunicorn on Linux)
# and runs the same bootstrap path as `python main.py`.
CMD ["python", "run_server.py"]
