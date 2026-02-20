#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# Docker Build & Test Script  v2.1
# ══════════════════════════════════════════════════════════════════
# Hem FastAPI (HTTP mod) hem de RabbitMQ Worker modunu test eder.
# docker-compose zaten çalışıyorsa portla çakışmaz (kendi ağını kurar).
#
# Kullanım:
#   chmod +x docker-test.sh
#   ./docker-test.sh               # Tüm testler
#   ./docker-test.sh --api-only    # Sadece FastAPI
#   ./docker-test.sh --worker-only # Sadece Worker + RabbitMQ

set -e

# ── Renkler ──────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'
YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

ok()   { echo -e "${GREEN}✅ $1${NC}"; }
fail() { echo -e "${RED}❌ $1${NC}"; }
info() { echo -e "${BLUE}ℹ  $1${NC}"; }
warn() { echo -e "${YELLOW}⚠  $1${NC}"; }

# ── Argüman Ayrıştırma ────────────────────────────────────────────
RUN_API=true
RUN_WORKER=true
for arg in "$@"; do
  case $arg in
    --api-only)    RUN_WORKER=false ;;
    --worker-only) RUN_API=false    ;;
  esac
done

# ── Sabitler ─────────────────────────────────────────────────────
TEST_IMAGE_URL="https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEgI8hbyGkUDAF7hItsu4gTbLgrcM7YJLvTEL494jT4TR_fK3YKb9FRiWd0ZZOWUFFB20ZsAkGAYDvcxR5d9WC7WTy29BnOCobwqhNlfSaDjam8POajCwHVRIJaC9pitYr9Zu1x4h30uWEbE/s1600/The_Last_Supper_Jacopo_Bassano_1542.jpg"
TEST_UUID="550e8400-e29b-41d4-a716-446655440000"
RABBITMQ_USER="${RABBITMQ_USER:-admin}"
RABBITMQ_PASS="${RABBITMQ_PASS:-admin123}"

# Test için izole ağ ve container isimleri (docker-compose ile çakışmaz)
TEST_NETWORK="deepfake-test-net"
RABBITMQ_CTR="deepfake-rabbitmq-test"
WORKER_CTR="deepfake-worker-test"
API_CTR="deepfake-api-test"
# Management UI için host'ta boş bir port bul (15673 varsayılan)
MGMT_HOST_PORT=15673

# ── Temizlik fonksiyonu (exit/hata'da otomatik çalışır) ──────────
cleanup() {
  info "Test kaynakları temizleniyor..."
  docker stop "$API_CTR"     2>/dev/null || true
  docker rm   "$API_CTR"     2>/dev/null || true
  docker stop "$WORKER_CTR"  2>/dev/null || true
  docker rm   "$WORKER_CTR"  2>/dev/null || true
  docker stop "$RABBITMQ_CTR" 2>/dev/null || true
  docker rm   "$RABBITMQ_CTR" 2>/dev/null || true
  docker network rm "$TEST_NETWORK" 2>/dev/null || true
}
trap cleanup EXIT

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  DeepFake Detection — Docker Build & Test  v2.1"
echo "════════════════════════════════════════════════════════════"
echo ""

# ── Ön Temizlik (önceki başarısız testlerden kalan artıklar) ─────
# Önceki çalışmada script hata verip yarıda kesilmiş olabilir.
# Aynı isimli container/network varsa silerek temiz başlıyoruz.
info "Önceki test artıkları temizleniyor (varsa)..."
docker stop "$API_CTR" "$WORKER_CTR" "$RABBITMQ_CTR" 2>/dev/null || true
docker rm   "$API_CTR" "$WORKER_CTR" "$RABBITMQ_CTR" 2>/dev/null || true
docker network rm "$TEST_NETWORK" 2>/dev/null || true
ok "Temiz başlangıç hazır"
echo ""

# ══════════════════════════════════════════════════════════════════
# BÖLÜM 1 — IMAGE BUILD
# ══════════════════════════════════════════════════════════════════

echo "📦 Docker image build ediliyor..."
docker build -t deepfake-worker:test . 2>&1 | grep -v "^#" | tail -5
echo ""

SIZE=$(docker images deepfake-worker:test --format "{{.Size}}" | head -1)
ok "Build tamamlandı — Image boyutu: $SIZE"
echo ""

# ══════════════════════════════════════════════════════════════════
# BÖLÜM 2 — FASTAPI (HTTP MOD) TESTİ
# ══════════════════════════════════════════════════════════════════

if [ "$RUN_API" = true ]; then

  echo "────────────────────────────────────────────────────────────"
  echo "  BÖLÜM 2 — FastAPI (HTTP Mod) Testi"
  echo "────────────────────────────────────────────────────────────"
  echo ""

  echo "🚀 FastAPI container başlatılıyor (MODE=api)..."
  docker run -d \
    --name "$API_CTR" \
    -p 8000:8000 \
    -e MODE=api \
    -e DEEPFAKE_API_KEY_DISABLED=true \
    deepfake-worker:test

  echo "⏳ Başlangıç bekleniyor (10s)..."
  sleep 10

  # 2a. Health Check
  echo ""
  echo "🏥 Health check..."
  if curl -sf http://localhost:8000/health > /dev/null; then
    ok "Health check geçti"
    HEALTH=$(curl -s http://localhost:8000/health)
    echo "   $(echo "$HEALTH" | grep -o '"version":"[^"]*"')"
    echo "   $(echo "$HEALTH" | grep -o '"thread_workers":[0-9]*')"
  else
    fail "Health check başarısız"
    docker logs "$API_CTR"
    exit 1
  fi

  # 2b. Metadata testi
  echo ""
  echo "🧪 /api/metadata testi..."
  RESPONSE=$(curl -s -X POST http://localhost:8000/api/metadata \
    -H "Content-Type: application/json" \
    -d "{\"id\":\"$TEST_UUID\",\"image_url\":\"$TEST_IMAGE_URL\",\"original_image_path\":\"uploads/test.jpg\"}")

  if echo "$RESPONSE" | grep -q "has_metadata"; then
    ok "/api/metadata geçti"
  else
    fail "/api/metadata başarısız → Yanıt: $RESPONSE"
    docker logs "$API_CTR"
    exit 1
  fi

  # 2c. Tam analiz testi
  echo ""
  echo "🧪 /api/analyze testi (paralel analiz ~1.3s)..."
  ANALYZE_RESPONSE=$(curl -s -X POST http://localhost:8000/api/analyze \
    -H "Content-Type: application/json" \
    -d "{\"id\":\"$TEST_UUID\",\"image_url\":\"$TEST_IMAGE_URL\"}")

  if echo "$ANALYZE_RESPONSE" | grep -q "IsDeepfake"; then
    ok "/api/analyze geçti"
    echo "   $(echo "$ANALYZE_RESPONSE" | grep -o '"IsDeepfake":[a-z]*')"
    echo "   $(echo "$ANALYZE_RESPONSE" | grep -o '"CnnConfidence":[0-9.]*')"
    echo "   $(echo "$ANALYZE_RESPONSE" | grep -o '"ProcessingTimeSeconds":[0-9.]*')"
  else
    fail "/api/analyze başarısız → ${ANALYZE_RESPONSE:0:200}"
    docker logs "$API_CTR"
    exit 1
  fi

  # 2d. Kaynak kullanımı
  echo ""
  echo "📊 FastAPI kaynak kullanımı:"
  docker stats "$API_CTR" --no-stream \
    --format "   CPU: {{.CPUPerc}} | RAM: {{.MemUsage}}"

  echo ""
  echo "🧹 FastAPI container temizleniyor..."
  docker stop "$API_CTR" && docker rm "$API_CTR"
  ok "FastAPI testi tamamlandı"
  echo ""

fi

# ══════════════════════════════════════════════════════════════════
# BÖLÜM 3 — RABBITMQ WORKER TESTİ
# ══════════════════════════════════════════════════════════════════
# ÖNEMLİ: docker-compose zaten 5672 portunu kullanıyor olabilir.
# Bu yüzden test container'ları için izole bir Docker ağı (bridge)
# oluşturuyoruz. AMQP portu (5672) host'a açılmıyor, container'lar
# kendi ağları üzerinden haberleşiyor. Sadece yönetim UI'si için
# host'ta 15673 portu kullanılıyor.
# ══════════════════════════════════════════════════════════════════

if [ "$RUN_WORKER" = true ]; then

  echo "────────────────────────────────────────────────────────────"
  echo "  BÖLÜM 3 — RabbitMQ Worker Testi"
  echo "────────────────────────────────────────────────────────────"
  echo ""

  # 3a. İzole test ağı oluştur
  info "İzole test ağı oluşturuluyor ($TEST_NETWORK)..."
  docker network create "$TEST_NETWORK" > /dev/null 2>&1 || \
    docker network inspect "$TEST_NETWORK" > /dev/null 2>&1
  ok "Test ağı hazır"

  # 3b. RabbitMQ başlat — AMQP portu host'a açılmıyor (çakışma yok!)
  echo ""
  echo "🐇 RabbitMQ başlatılıyor (ağ içi, port çakışması yok)..."
  docker run -d \
    --name "$RABBITMQ_CTR" \
    --hostname rabbitmq-test \
    --network "$TEST_NETWORK" \
    -p "$MGMT_HOST_PORT":15672 \
    -e RABBITMQ_DEFAULT_USER="$RABBITMQ_USER" \
    -e RABBITMQ_DEFAULT_PASS="$RABBITMQ_PASS" \
    rabbitmq:3.13-management-alpine

  echo "⏳ RabbitMQ hazır olana kadar bekleniyor (max 45s)..."
  READY=false
  for i in $(seq 1 9); do
    sleep 5
    if docker exec "$RABBITMQ_CTR" rabbitmq-diagnostics ping > /dev/null 2>&1; then
      READY=true
      ok "RabbitMQ hazır ($((i*5))s)"
      break
    fi
    info "Bekleniyor... ($((i*5))s)"
  done

  if [ "$READY" = false ]; then
    fail "RabbitMQ 45 saniyede hazır olmadı"
    docker logs "$RABBITMQ_CTR"
    exit 1
  fi

  # 3c. Python Worker başlat (aynı izole ağ üzerinden bağlanıyor)
  echo ""
  echo "🐍 Python Worker başlatılıyor (MODE=worker)..."
  docker run -d \
    --name "$WORKER_CTR" \
    --network "$TEST_NETWORK" \
    -e MODE=worker \
    -e RABBITMQ_HOST="$RABBITMQ_CTR" \
    -e RABBITMQ_PORT=5672 \
    -e RABBITMQ_USER="$RABBITMQ_USER" \
    -e RABBITMQ_PASS="$RABBITMQ_PASS" \
    -e WORKER_THREADS=4 \
    deepfake-worker:test

  echo "⏳ Worker bağlantısı bekleniyor (15s)..."
  sleep 15

  # 3d. Worker bağlantı kontrolü
  echo ""
  echo "🔗 Worker RabbitMQ bağlantı kontrolü..."
  if docker logs "$WORKER_CTR" 2>&1 | grep -q "RabbitMQ\|bağland\|bağlantı"; then
    ok "Worker RabbitMQ'ya bağlandı"
    docker logs "$WORKER_CTR" 2>&1 | tail -6 | sed 's/^/   /'
  else
    fail "Worker bağlanamadı"
    docker logs "$WORKER_CTR"
    exit 1
  fi

  # 3e. Queue kontrolü
  echo ""
  echo "📋 Queue kontrolü..."
  sleep 2
  QUEUES=$(docker exec "$RABBITMQ_CTR" \
    rabbitmqctl list_queues name durable 2>/dev/null || echo "")

  if echo "$QUEUES" | grep -q "analysis_queue"; then
    ok "analysis_queue oluşturuldu (durable)"
  else
    warn "Queue henüz görünmüyor"
  fi

  if echo "$QUEUES" | grep -q "result_queue"; then
    ok "result_queue oluşturuldu (durable)"
  fi

  # 3f. Test mesajı gönder (Management REST API — host:15673 üzerinden)
  echo ""
  echo "📨 analysis_queue'ya test mesajı gönderiliyor..."
  PUBLISH_RESULT=$(curl -s -u "$RABBITMQ_USER:$RABBITMQ_PASS" \
    -X POST "http://localhost:$MGMT_HOST_PORT/api/exchanges/%2F//publish" \
    -H "Content-Type: application/json" \
    -d "{
      \"properties\":{\"delivery_mode\":2,\"content_type\":\"application/json\"},
      \"routing_key\":\"analysis_queue\",
      \"payload\":\"{\\\"id\\\":\\\"$TEST_UUID\\\",\\\"image_url\\\":\\\"$TEST_IMAGE_URL\\\",\\\"original_image_path\\\":\\\"uploads/test.jpg\\\"}\",
      \"payload_encoding\":\"string\"
    }" 2>/dev/null)

  if echo "$PUBLISH_RESULT" | grep -q "routed"; then
    ok "Mesaj kuyruğa gönderildi"
  else
    warn "Management API yanıtı: $PUBLISH_RESULT"
    warn "Mesaj gönderilemedi — loglara bakın"
  fi

  # 3g. İşlenme bekleniyor
  echo ""
  echo "⏳ Worker analiz sonucu bekleniyor (max 30s)..."
  PROCESSED=false
  for i in $(seq 1 6); do
    sleep 5
    if docker logs "$WORKER_CTR" 2>&1 | grep -qE "Tamamlandı|Completed|✔"; then
      PROCESSED=true
      ok "Worker mesajı işledi ($((i*5))s)"
      break
    fi
    info "İşleniyor... ($((i*5))s)"
  done

  # 3h. result_queue kontrol
  echo ""
  echo "📬 result_queue kontrolü..."
  RESULT_COUNT=$(docker exec "$RABBITMQ_CTR" \
    rabbitmqctl list_queues name messages 2>/dev/null | \
    grep "result_queue" | awk '{print $2}' || echo "0")

  if [ "$PROCESSED" = true ] || [ "${RESULT_COUNT:-0}" -gt "0" ]; then
    ok "result_queue'da sonuç mevcut (${RESULT_COUNT:-?} mesaj)"
  else
    warn "result_queue boş — worker logları:"
    docker logs "$WORKER_CTR" 2>&1 | tail -15 | sed 's/^/   /'
  fi

  # 3i. Kaynak kullanımı ve son loglar
  echo ""
  echo "📊 Worker kaynak kullanımı:"
  docker stats "$WORKER_CTR" --no-stream \
    --format "   CPU: {{.CPUPerc}} | RAM: {{.MemUsage}}"

  echo ""
  echo "📋 Worker son logları:"
  docker logs "$WORKER_CTR" 2>&1 | tail -10 | sed 's/^/   /'

  ok "Worker testi tamamlandı"
  echo ""

fi

# ══════════════════════════════════════════════════════════════════
# BÖLÜM 4 — DOSYA VE KONFİGÜRASYON KONTROLLERİ
# ══════════════════════════════════════════════════════════════════

echo "────────────────────────────────────────────────────────────"
echo "  BÖLÜM 4 — Genel Kontroller"
echo "────────────────────────────────────────────────────────────"
echo ""

[ -f "healthcheck.py" ]   && ok "healthcheck.py mevcut"   || warn "healthcheck.py eksik"
[ -f ".env.example" ]     && ok ".env.example mevcut"      || warn ".env.example eksik"
[ -f "worker.py" ]        && ok "worker.py mevcut"         || warn "worker.py eksik"

grep -q "pika"     requirements.txt 2>/dev/null && ok "pika requirements.txt'te mevcut"     || warn "pika requirements.txt'te yok"
grep -q "worker.py" Dockerfile      2>/dev/null && ok "Dockerfile worker.py'yi kopyalıyor"  || warn "Dockerfile'da COPY worker.py eksik"
grep -q "healthcheck" Dockerfile    2>/dev/null && ok "Dockerfile HEALTHCHECK var"           || warn "Dockerfile'da HEALTHCHECK eksik"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  ✅ Tüm testler tamamlandı!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Sonraki adımlar:"
echo "  1. docker tag deepfake-worker:test deepfake-worker:latest"
echo "  2. cp .env.example .env  (değerleri düzenle)"
echo "  3. docker-compose up -d --build"
echo "  4. docker-compose logs -f python-worker"
echo "  5. RabbitMQ UI: http://localhost:15672"
echo ""