# ══════════════════════════════════════════════════════════════════
# DeepFake Python Worker – Dockerfile
# ══════════════════════════════════════════════════════════════════
# Multi-stage build:
#   1. builder  → bağımlılıkları kurar (derleme araçları burada kalır)
#   2. runtime  → yalnızca çalışma zamanı gereksinimleri (küçük imaj)
# ══════════════════════════════════════════════════════════════════

# ── Stage 1: Builder ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Sistem bağımlılıkları (OpenCV için libGL gerekli)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Önce requirements — Docker cache katmanı (kod değişse bile pip çalışmaz)
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="cihanoren <https://github.com/cihanoren>"
LABEL description="DeepFake Detection – RabbitMQ Async Worker"
LABEL version="3.0.0"

# Çalışma zamanı sistem bağımlılıkları
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Builder'dan kurulu paketleri kopyala
COPY --from=builder /install /usr/local

WORKDIR /app

# Kaynak kodu kopyala
COPY src/ ./src/

# Güvenlik: root olmayan kullanıcı
RUN useradd --no-create-home --shell /bin/false worker
USER worker

# ── Sağlık Kontrolü ───────────────────────────────────────────────
# pika ile RabbitMQ TCP bağlantısını test eder
HEALTHCHECK \
    --interval=30s \
    --timeout=10s \
    --start-period=20s \
    --retries=3 \
    CMD python -c "\
import os, socket; \
s = socket.create_connection(\
    (os.getenv('RABBITMQ_HOST','rabbitmq'), int(os.getenv('RABBITMQ_PORT','5672'))),\
    timeout=5\
); s.close(); print('OK')"

# ── Giriş Noktası ─────────────────────────────────────────────────
CMD ["python", "-m", "src.worker.main"]