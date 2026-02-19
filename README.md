# DeepFake-python

DeepFake / Yapay görsel tespiti için FastAPI tabanlı analiz servisi.  
**(Bitirme Projesi)**

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com)

---

## 📐 Proje Yapısı

```
DeepFake-python/
│
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI uygulama + route'lar + API Key middleware
│   └── models.py        # Pydantic modelleri
│
├── analysis/
│   ├── __init__.py
│   ├── error_level_analysis.py     # ELA
│   ├── fast_fourier_transform.py   # FFT
│   ├── metadata_analyzer.py        # EXIF / Metadata
│   └── model_simulator.py          # CNN simülasyonu + Grad-CAM
│
├── benchmark.py         # Performans testi
├── benchmark_viewer.py  # HTML görsel rapor üretici
├── requirements.txt
├── .env.example         # Ortam değişkenleri şablonu
├── Dockerfile           # Multi-stage production build
├── .dockerignore
├── docker-compose.yml
└── README.md
```

---

## 🚀 Hızlı Başlangıç

### Docker ile (Önerilen)

```bash
# 1. Projeyi klonla
git clone https://github.com/cihanoren/DeepFake-python.git
cd DeepFake-python

# 2. Environment hazırla
cp .env.example .env

# 3. Docker Compose ile başlat
docker-compose up -d

# 4. Swagger UI'da test et
open http://localhost:8000/docs
```

**Alternatif: Manuel Docker**

```bash
# Build
docker build -t deepfake-api:latest .

# Run
docker run --rm -p 8000:8000 \
  -e DEEPFAKE_API_KEY_DISABLED=true \
  deepfake-api:latest
```

---

## 🐳 Docker Deployment

### Production Ortamı

**1. Environment Ayarları**

`.env` dosyasını oluştur:

```env
DEEPFAKE_API_KEY_DISABLED=false
DEEPFAKE_API_KEY=your-super-secret-production-key-here
PYTHONUNBUFFERED=1
```

**2. Docker Compose ile Deploy**

```bash
# Arka planda başlat
docker-compose up -d

# Log'ları izle
docker-compose logs -f deepfake-api

# Status kontrol
docker-compose ps

# Durdur
docker-compose down
```

**3. Manuel Deployment**

```bash
# Build (tag'li)
docker build -t deepfake-api:3.1.0 .

# Production run
docker run -d \
  --name deepfake-api \
  --restart unless-stopped \
  -p 8000:8000 \
  -e DEEPFAKE_API_KEY_DISABLED=false \
  -e DEEPFAKE_API_KEY="production-key-xyz" \
  --memory="2g" \
  --cpus="2.0" \
  deepfake-api:3.1.0
```

### Docker Komutları

```bash
# Container'a shell ile gir
docker exec -it deepfake-api /bin/bash

# Gerçek zamanlı log
docker logs -f deepfake-api

# Kaynak kullanımı
docker stats deepfake-api

# Health check status
docker inspect --format='{{.State.Health.Status}}' deepfake-api

# Container yeniden başlat
docker restart deepfake-api

# Temizlik
docker-compose down -v
docker system prune -a
```

### Image Optimizasyonu

| Build Yöntemi | Image Boyutu | Açıklama |
|---------------|--------------|----------|
| Single-stage | ~1.2 GB | Tüm build tools dahil |
| **Multi-stage** | **~450 MB** | Sadece runtime (kullanılan) |
| Alpine | ~300 MB | OpenCV derlemesi gerekir (yavaş) |

---

## 💻 Lokal Geliştirme

Docker kullanmadan yerel ortamda çalıştırma:

### 1️⃣ Sanal Ortam Oluştur

**macOS / Linux**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows**
```bash
python -m venv venv
venv\Scripts\activate
```

### 2️⃣ Bağımlılıkları Yükle

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3️⃣ Environment Ayarla

```bash
cp .env.example .env
# .env içinde DEEPFAKE_API_KEY_DISABLED=true yap
```

### 4️⃣ Sunucuyu Başlat

**Development (auto-reload):**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Production:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

> ⚠️ **macOS:** `--workers 1` kullanın (ThreadPoolExecutor zaten paralel çalışır)

---

## 🔑 API Güvenliği

### API Key Kullanımı

Tüm `/api/*` endpoint'leri `X-API-Key` header gerektirir.

**cURL Örneği:**

```bash
curl -X POST "http://localhost:8000/api/analyze" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-secret-key-change-me" \
  -d '{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "image_url": "https://example.com/photo.jpg",
    "original_image_path": "uploads/photo.jpg"
  }'
```

### Key Kontrolünü Yönetme

| Ortam | `DEEPFAKE_API_KEY_DISABLED` | Kullanım |
|-------|----------------------------|----------|
| Development | `true` | Swagger serbestçe çalışır |
| Staging | `false` | Test key ile korumalı |
| Production | `false` | Güçlü key zorunlu |

**Swagger'da Test:**

1. `.env` → `DEEPFAKE_API_KEY_DISABLED=true`
2. `docker-compose restart`
3. http://localhost:8000/docs → direkt test et

**Production'da Güvenlik:**

```env
DEEPFAKE_API_KEY_DISABLED=false
DEEPFAKE_API_KEY=$(openssl rand -hex 32)  # 64 karakter random key
```

---

## 📚 API Dokümantasyonu

### Endpoints

| Method | Endpoint | Açıklama | Auth | Timeout |
|--------|----------|----------|------|---------|
| POST | `/api/analyze` | Tüm analizler (paralel) | ✓ | 60s |
| POST | `/api/ela` | Sadece ELA | ✓ | 15s |
| POST | `/api/fft` | Sadece FFT | ✓ | 15s |
| POST | `/api/metadata` | Sadece Metadata | ✓ | 5s |
| POST | `/api/model` | Sadece Model + Grad-CAM | ✓ | 15s |
| GET | `/health` | Sağlık kontrolü | ✗ | 1s |
| GET | `/docs` | Swagger UI | ✗ | - |

### İstek Formatı

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "image_url": "https://api.example.com/uploads/photo.jpg",
  "original_image_path": "uploads/photo.jpg"
}
```

**Alanlar:**
- `id` (UUID): .NET tarafından üretilir
- `image_url` (string): Python'ın erişebileceği URL
- `original_image_path` (string): .NET sunucusundaki fiziksel yol

### Yanıt Örneği

```json
{
  "Id": "550e8400-e29b-41d4-a716-446655440000",
  "IsDeepfake": true,
  "CnnConfidence": 0.8756,
  "ElaScore": 0.6234,
  "FftAnomalyScore": 0.7123,
  "ExifHasMetadata": false,
  "ExifCameraInfo": null,
  "ExifSuspiciousIndicators": "EXIF verisi yok;Kamera bilgisi eksik",
  "GradcamImageBase64": "<base64 JPEG>",
  "ElaImageBase64": "<base64 JPEG>",
  "FftImageBase64": "<base64 JPEG>",
  "ProcessingTimeSeconds": 3.45,
  "Status": "Completed"
}
```

> **Not:** Python base64 döner, .NET diske yazar → DB'deki `*Path` sütunlarını günceller.

---

## ⚡ Performans & Benchmark

### Hızlı Test

```bash
# Sunucu hazır mı kontrol
curl http://localhost:8000/health

# Temel benchmark (5 istek)
python3 benchmark.py

# Detaylı test
python3 benchmark.py --url https://example.com/photo.jpg --n 10
```

### Görsel Analiz Raporu

```bash
python3 benchmark_viewer.py
```

- `analysis_result.html` oluşturur
- Browser'da otomatik açar
- Grad-CAM, ELA, FFT görsellerini gösterir
- Interaktif lightbox (tıklayarak büyüt)

### Beklenen Performans

| Analiz | Süre (avg) | Paralel mi? |
|--------|-----------|-------------|
| Model + Grad-CAM | ~1.2s | Evet |
| ELA | ~1.0s | Evet |
| FFT | ~0.9s | Evet |
| Metadata | ~0.1s | Evet |
| **Toplam** | **~1.3s** | ✓ ThreadPool |

**Kaynak Kullanımı:**
- Baseline Memory: ~512 MB
- Peak Memory: ~1.2 GB (paralel analiz sırasında)
- CPU: ~80% (4 thread aktif)

---

## 🏗 Mimari

### Sistem Akışı

```
┌─────────────┐
│  Kullanıcı  │
│ (Web/Mobile)│
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  .NET Core API  │
├─────────────────┤
│ 1. Görsel kaydet│ ← uploads/img123.jpg
│ 2. DB: INSERT   │ ← Status='Processing'
│ 3. Python çağır │
└────────┬────────┘
         │ HTTP POST
         │ {id, image_url, original_image_path}
         ▼
┌──────────────────────┐
│   Python FastAPI     │
├──────────────────────┤
│ ⚡ Paralel Analiz:   │
│  • Model (CNN)       │
│  • ELA               │
│  • FFT               │
│  • Metadata          │
└────────┬─────────────┘
         │ JSON Response
         │ {base64 images, scores}
         ▼
┌─────────────────┐
│  .NET Core API  │
├─────────────────┤
│ 4. Base64→Disk  │ ← gradcam.jpg, ela.jpg...
│ 5. Thumbnail    │ ← 150x150 px
│ 6. DB: UPDATE   │ ← Status='Completed', *Path
└────────┬────────┘
         │
         ▼
┌─────────────┐
│  Kullanıcı  │ ← Sonuçları göster
└─────────────┘
```

### Sorumluluk Dağılımı

| Görev | Python | .NET |
|-------|--------|------|
| **Görsel İndirme** | ✓ | ✗ |
| **CNN Analizi** | ✓ | ✗ |
| **ELA/FFT/Metadata** | ✓ | ✗ |
| **Grad-CAM Üretimi** | ✓ | ✗ |
| **Diske Yazma** | ✗ | ✓ |
| **Thumbnail Oluşturma** | ✗ | ✓ |
| **DB Yönetimi** | ✗ | ✓ |
| **ID Üretimi** | ✗ | ✓ |

> **Anahtar Prensip:** Python **stateless**, .NET **stateful**

---

## 🧠 Teknik Detaylar

### Stack

- **Framework:** FastAPI 0.109.0
- **ASGI Server:** Uvicorn
- **Paralel İşleme:** ThreadPoolExecutor (4-16 thread)
- **Görsel İşleme:** OpenCV 4.9, Pillow 10.3+
- **Analiz:** NumPy 1.26, Custom algorithms
- **HTTP Client:** httpx 0.26 (async)

### Özellikler

✅ **Stateless Design** — disk yazımı yok  
✅ **Paralel Analiz** — ThreadPool ile 4 yöntem eşzamanlı  
✅ **API Key Middleware** — production-ready güvenlik  
✅ **Timeout Yönetimi** — 60s limit  
✅ **Error Handling** — DB'ye `Failed` status  
✅ **Docker Multi-stage** — optimize image (~450MB)  
✅ **Health Check** — `/health` endpoint + Docker healthcheck  
✅ **Non-root User** — container security  

### Sistem Gereksinimleri

| Ortam | CPU | RAM | Disk | Network |
|-------|-----|-----|------|---------|
| Development | 2 core | 2 GB | 10 GB | 10 Mbps |
| Production | 4 core | 4 GB | 20 GB | 100 Mbps |
| Docker | 2 core | 2 GB | 10 GB | - |

---

## 🔧 Sorun Giderme

### Docker Build Hataları

**Problem:** OpenCV kurulumu başarısız

```bash
# Çözüm: Build cache temizle
docker builder prune
docker build --no-cache -t deepfake-api:latest .
```

**Problem:** Permission denied

```bash
# Çözüm: Non-root user ayarları doğru yapıldı mı kontrol et
docker run --rm deepfake-api:latest id
# Çıktı: uid=1000(deepfake) gid=1000(deepfake) groups=1000(deepfake)
```

### Runtime Hataları

**Problem:** `ImportError: libGL.so.1`

```bash
# Dockerfile'da eksik → zaten düzeltildi
# libgl1, libglib2.0-0, libsm6, libxext6 eklendi
```

**Problem:** API Key 401 hatası

```bash
# .env kontrol
cat .env | grep DEEPFAKE_API_KEY_DISABLED
# true olmalı (development) veya doğru key gönderilmeli
```

### Performans Sorunları

**Problem:** Analiz 5+ saniye sürüyor

```bash
# CPU limit kontrol
docker stats deepfake-api

# Limit artır
docker update --cpus="4.0" --memory="4g" deepfake-api
```

---



## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/amazing`)
3. Commit yapın (`git commit -m 'feat: Add amazing feature'`)
4. Push edin (`git push origin feature/amazing`)
5. Pull Request açın

---

## 📧 İletişim

**Proje Sahibipleri:**[alikoroglu](https://github.com/alikorogluts)
                      [cihanoren](https://github.com/cihanoren)

**Sorun Bildirme:** [GitHub Issues](https://github.com/cihanoren/DeepFake-python/issues)

---

**Not:** Bu servis sadece analiz yapar, veri saklamaz. Tüm dosya yönetimi ve veritabanı işlemleri .NET Core API tarafındadır.