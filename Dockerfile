# ============================================
# Bonded Exhibition Chatbot - Production Dockerfile
# Multi-stage build, cross-platform (linux/amd64 + linux/arm64)
# ============================================

# --- Stage 1: Builder ---
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

# Build dependencies (cleaned up afterward in this stage only)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install Python packages to a prefix directory for copy into runtime
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2: Runtime ---
FROM python:3.11-slim-bookworm AS production

LABEL org.opencontainers.image.title="bonded-exhibition-chatbot"
LABEL org.opencontainers.image.description="FAQ & Policy chatbot for Korean bonded exhibition halls"
LABEL org.opencontainers.image.source="https://github.com/sun475300-sudo/bonded-exhibition-chatbot-data"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Runtime-only dependencies; create non-root user with stable UID for volume permissions
RUN apt-get update && apt-get install -y --no-install-recommends \
        sqlite3 curl tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 chatbot \
    && useradd  --uid 1000 --gid chatbot --create-home --home-dir /home/chatbot --shell /bin/bash chatbot

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code (own as chatbot to allow writes to logs/data without root)
COPY --chown=chatbot:chatbot . .

<<<<<<< HEAD
# Create runtime directories that bind mounts may not auto-create
RUN mkdir -p logs data backups .hf-cache \
    && chown -R chatbot:chatbot /app

# Default environment (override via .env / compose / -e)
=======
# Create required directories (incl. HuggingFace cache for sentence-transformers)
RUN mkdir -p logs data backups /app/.hf_cache \
    && chown -R chatbot:chatbot /app

# Environment defaults
# - HF_HOME: HuggingFace model cache (mount as volume to persist between rebuilds)
# - GUNICORN_*: tuned for small-VM deployment (2 workers x 4 threads)
>>>>>>> claude/cross-platform-setup-20260428085407
ENV CHATBOT_PORT=8080 \
    CHATBOT_HOST=0.0.0.0 \
    CHATBOT_DEBUG=false \
    CHATBOT_LOG_LEVEL=INFO \
    CHATBOT_DB_PATH=logs/chat_logs.db \
<<<<<<< HEAD
    HF_HOME=/app/.hf-cache \
=======
    HF_HOME=/app/.hf_cache \
    TRANSFORMERS_CACHE=/app/.hf_cache \
    GUNICORN_WORKERS=2 \
    GUNICORN_THREADS=4 \
    GUNICORN_TIMEOUT=120 \
    GUNICORN_BIND=0.0.0.0:8080 \
>>>>>>> claude/cross-platform-setup-20260428085407
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

EXPOSE 8080

<<<<<<< HEAD
# Healthcheck reuses the project script (covers /api/health + FAQ count)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python deploy/healthcheck.py --host 127.0.0.1 --port "${CHATBOT_PORT}" || exit 1
=======
# Health check uses /api/health endpoint (curl is cheaper than spawning python)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${CHATBOT_PORT}/api/health" || exit 1
>>>>>>> claude/cross-platform-setup-20260428085407

USER chatbot

# tini handles PID 1 signal forwarding so Ctrl+C / docker stop work cleanly
ENTRYPOINT ["tini", "--"]

# 2 workers x 4 threads + --preload (single FAQ load shared across workers via fork)
CMD ["sh", "-c", "gunicorn --bind ${GUNICORN_BIND} --workers ${GUNICORN_WORKERS} --threads ${GUNICORN_THREADS} --timeout ${GUNICORN_TIMEOUT} --preload --access-logfile - --error-logfile - web_server:app"]
