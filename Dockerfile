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
# Create requir