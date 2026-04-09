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

# Create required directories
RUN mkdir -p logs data backups \
    && chown -R chatbot:chatbot /app

# Environment defaults
ENV CHATBOT_PORT=8080 \
    CHATBOT_HOST=0.0.0.0 \
    CHATBOT_DEBUG=false \
    CHATBOT_LOG_LEVEL=INFO \
    CHATBOT_DB_PATH=logs/chat_logs.db \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python deploy/healthcheck.py --host 127.0.0.1 --port ${CHATBOT_PORT} || exit 1

# Run as non-root user
USER chatbot

# Use tini as init process (handles signals properly)
ENTRYPOINT ["tini", "--"]

CMD ["gunicorn", "-c", "deploy/gunicorn_config.py", "web_server:app"]
