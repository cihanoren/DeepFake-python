# ══════════════════════════════════════════════════════════════════
# Deepfake Detection – Production Dockerfile
# Multi-stage build: ~450MB final image
#
# Çalışma Modları (MODE env değişkeniyle seçilir):
#   MODE=api    → uvicorn app.main:app  (varsayılan)
#   MODE=worker → python worker.py
# ══════════════════════════════════════════════════════════════════

# ── Stage 1: Builder ─────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ── Stage 2: Runtime ─────────────────────────────────────────────
FROM python:3.11-slim

LABEL maintainer="cihanoren/alikorogluts"
LABEL description="Deepfake Detection – FastAPI & RabbitMQ Worker"
LABEL version="3.2.0"

WORKDIR /app

# Runtime bağımlılıkları (OpenCV + curl health check için)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxext6 libxrender1 libgomp1 libgl1 curl \
    && rm -rf /var/lib/apt/lists/*

# Python wheel'lerini builder'dan al
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* && \
    rm -rf /wheels

# Uygulama kodunu kopyala
COPY app/           /app/app/
COPY analysis/      /app/analysis/
COPY worker.py      /app/worker.py
COPY healthcheck.py /app/healthcheck.py

# Non-root kullanıcı (güvenlik)
RUN useradd -m -u 1000 -s /bin/bash deepfake && \
    chown -R deepfake:deepfake /app
USER deepfake

# ── Hassas bilgi içermeyen güvenli env değişkenleri ──────────────
# API key ve şifreler buraya yazılmıyor — docker-compose veya
# runtime'da -e / --env-file ile verilmeli.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MODE=api \
    RABBITMQ_HOST=rabbitmq \
    RABBITMQ_PORT=5672 \
    WORKER_THREADS=4

# ── Health Check ─────────────────────────────────────────────────
# API modu  → HTTP /health endpoint kontrolü
# Worker modu → RabbitMQ bağlantı + queue kontrolü (healthcheck.py)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD sh -c '\
        if [ "$MODE" = "worker" ]; then \
            python healthcheck.py; \
        else \
            curl -f http://localhost:8000/health || exit 1; \
        fi'

EXPOSE 8000

# MODE değişkenine göre başlat
CMD ["sh", "-c", \
    "if [ \"$MODE\" = 'worker' ]; then \
        echo '>>> WORKER MODU BAŞLATIYOR...'; \
        python worker.py; \
    else \
        echo '>>> API MODU BAŞLATIYOR...'; \
        uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1; \
    fi"]