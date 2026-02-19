#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# Docker Build & Test Script
# ══════════════════════════════════════════════════════════════════
# Usage:
#   chmod +x docker-test.sh
#   ./docker-test.sh

set -e  # Exit on error

echo "════════════════════════════════════════════════════════════"
echo "  DeepFake API - Docker Build & Test"
echo "════════════════════════════════════════════════════════════"
echo ""

# ── 1. Build ─────────────────────────────────────────────────────
echo "📦 Building Docker image..."
docker build -t deepfake-api:test .

# Image boyutunu göster
SIZE=$(docker images deepfake-api:test --format "{{.Size}}")
echo "✅ Build complete: $SIZE"
echo ""

# ── 2. Start Container ───────────────────────────────────────────
echo "🚀 Starting container..."
docker run -d \
  --name deepfake-test \
  -p 8000:8000 \
  -e DEEPFAKE_API_KEY_DISABLED=true \
  deepfake-api:test

echo "⏳ Waiting for startup (10s)..."
sleep 10

# ── 3. Health Check ──────────────────────────────────────────────
echo ""
echo "🏥 Health check..."
if curl -f http://localhost:8000/health 2>/dev/null; then
  echo "✅ Health check passed"
else
  echo "❌ Health check failed"
  docker logs deepfake-test
  docker stop deepfake-test
  docker rm deepfake-test
  exit 1
fi

# ── 4. API Test ──────────────────────────────────────────────────
echo ""
echo "🧪 Testing /api/metadata endpoint..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/metadata \
  -H "Content-Type: application/json" \
  -d '{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "image_url": "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEgI8hbyGkUDAF7hItsu4gTbLgrcM7YJLvTEL494jT4TR_fK3YKb9FRiWd0ZZOWUFFB20ZsAkGAYDvcxR5d9WC7WTy29BnOCobwqhNlfSaDjam8POajCwHVRIJaC9pitYr9Zu1x4h30uWEbE/s1600/The_Last_Supper_Jacopo_Bassano_1542.jpg",
    "original_image_path": "uploads/test.jpg"
  }')

if echo "$RESPONSE" | grep -q "has_metadata"; then
  echo "✅ API test passed"
else
  echo "❌ API test failed"
  echo "Response: $RESPONSE"
  docker logs deepfake-test
  docker stop deepfake-test
  docker rm deepfake-test
  exit 1
fi

# ── 5. Resource Check ────────────────────────────────────────────
echo ""
echo "📊 Resource usage:"
docker stats deepfake-test --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# ── 6. Cleanup ───────────────────────────────────────────────────
echo ""
echo "🧹 Cleaning up..."
docker stop deepfake-test
docker rm deepfake-test

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  ✅ All tests passed!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. docker tag deepfake-api:test deepfake-api:latest"
echo "  2. docker-compose up -d"
echo ""
