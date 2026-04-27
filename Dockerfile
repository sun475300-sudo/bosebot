# ============================================
# 보세전시장 챗봇 - Production Dockerfile
# Multi-stage build for minimal image size
# ============================================

# --- Stage 1: Builder ---
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install Python packages to a prefix directory
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2: Production ---
FROM python:3.11-slim AS production

LABEL maintainer="sun475300@gmail.com"
LABEL description="보세전시장 챗봇 - FAQ & Policy Chatbot"
LABEL version="2.0.0"

WORKDIR /app

# Runtime dependencies only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 curl tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r chatbot && useradd -r -g chatbot -d /app chatbot

# Copy Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=chatbot:chatbot . .

# Create required directories (incl. HuggingFace cache for sentence-transformers)
RUN mkdir -p logs data backups /app/.hf_cache \
    && chown -R chatbot:chatbot /app

# Environment defaults
# - HF_HOME: HuggingFace model cache (mount as volume to persist between rebuilds)
# - GUNICORN_*: tuned for small-VM deployment (2 workers x 4 threads)
ENV CHATBOT_PORT=8080 \
    CHATBOT_HOST=0.0.0.0 \
    CHATBOT_DEBUG=false \
    CHATBOT_LOG_LEVEL=INFO \
    CHATBOT_DB_PATH=logs/chat_logs.db \
    HF_HOME=/app/.hf_cache \
    TRANSFORMERS_CACHE=/app/.hf_cache \
    GUNICORN_WORKERS=2 \
    GUNICORN_THREADS=4 \
    GUNICORN_TIMEOUT=120 \
    GUNICORN_BIND=0.0.0.0:8080 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

# Health check uses /api/health endpoint (curl is cheaper than spawning python)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${CHATBOT_PORT}/api/health" || exit 1

# Run as non-root user
USER chatbot

# Use tini as init process (handles signals properly)
ENTRYPOINT ["tini", "--"]

# 2 workers x 4 threads + --preload (single FAQ load shared across workers via fork)
CMD ["sh", "-c", "gunicorn --bind ${GUNICORN_BIND} --workers ${GUNICORN_WORKERS} --threads ${GUNICORN_THREADS} --timeout ${GUNICORN_TIMEOUT} --preload --access-logfile - --error-logfile - web_server:app"]
