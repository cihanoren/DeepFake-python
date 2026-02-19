# ══════════════════════════════════════════════════════════════════
# Deepfake Detection API - Production Dockerfile
# ══════════════════════════════════════════════════════════════════
# Multi-stage build: ~450MB final image (vs ~1.2GB single-stage)

# ── Stage 1: Builder ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────
FROM python:3.11-slim

# Metadata
LABEL maintainer="cihanoren"
LABEL description="Deepfake Detection API - FastAPI analysis service"
LABEL version="3.1.0"

WORKDIR /app

# Runtime dependencies (OpenCV + curl for health check)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libgl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages from builder
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* && \
    rm -rf /wheels

# Copy application code
COPY app /app/app
COPY analysis /app/analysis

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash deepfake && \
    chown -R deepfake:deepfake /app

USER deepfake

# Environment defaults (override with -e or .env)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEEPFAKE_API_KEY_DISABLED=false \
    DEEPFAKE_API_KEY=change-me-in-production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Production command (single worker for ThreadPoolExecutor)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]