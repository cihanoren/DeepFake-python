# DeepFake-python

DeepFake / Yapay görsel tespiti için FastAPI tabanlı analiz servisi.  
(Proje: Bitirme Projesi)

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
├── benchmark_viewer.py  # Çıktı analizli performans testi
├── requirements.txt
├── .env.example         # Ortam değişkenleri şablonu
└── README.md
```

---

## 🚀 Çalıştırma

### 1️⃣ Projeyi klonla

```bash
git clone https://github.com/cihanoren/DeepFake-python.git
cd DeepFake-python
```

### 2️⃣ Sanal ortam oluştur ve aktif et

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

### 3️⃣ Ortam değişkenlerini ayarla

```bash
cp .env.example .env
```

`.env` dosyasını düzenle:

```env
# Swagger'da test için kapalı bırak
DEEPFAKE_API_KEY_DISABLED=true

# Production'da mutlaka değiştir
DEEPFAKE_API_KEY=dev-secret-key-change-me
```

### 4️⃣ Bağımlılıkları yükle

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## ▶️ Sunucuyu Çalıştırma

### 🔧 Development Modu

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 🚀 Production Modu

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

> ⚠️ **macOS:** `--workers 1` kullanın. ThreadPoolExecutor zaten paralel işleme sağlar.

---

## 🔑 API Key Kullanımı

Tüm `/api/*` route'ları `X-API-Key` header gerektirir.

```bash
# Key ile istek
curl -X POST "http://localhost:8000/api/analyze" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-secret-key-change-me" \
  -d '{"id": "550e8400-e29b-41d4-a716-446655440000", "image_url": "https://example.com/photo.jpg"}'
```

### Key Kontrolünü Kapatma (Swagger / Test)

`.env` dosyasında:
```env
DEEPFAKE_API_KEY_DISABLED=true
```

veya çalıştırırken:
```bash
DEEPFAKE_API_KEY_DISABLED=true uvicorn app.main:app --reload --port 8000
```

| `DEEPFAKE_API_KEY_DISABLED` | Davranış |
|-----------------------------|----------|
| `true`                      | Key kontrolü yok, Swagger serbestçe çalışır |
| `false` (varsayılan)        | Her `/api/*` isteğinde `X-API-Key` zorunlu |

---

## 🔗 Route'lar

| Method | Endpoint          | Açıklama                        |
|--------|-------------------|---------------------------------|
| POST   | `/api/analyze`    | Tüm analizler (paralel)         |
| POST   | `/api/ela`        | Sadece ELA analizi              |
| POST   | `/api/fft`        | Sadece FFT analizi              |
| POST   | `/api/metadata`   | Sadece Metadata / EXIF          |
| POST   | `/api/model`      | Sadece Model + Grad-CAM         |
| GET    | `/health`         | Sağlık kontrolü (key gereksiz)  |
| GET    | `/docs`           | Swagger UI (key gereksiz)       |

### İstek Formatı (tüm POST route'lar)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "image_url": "https://example.com/photo.jpg"
}
```

> `id` → .NET tarafından üretilir ve gönderilir. Python tarafı asla UUID üretmez.

### Yanıt Örneği (`/api/analyze`)

```json
{
  "Id":                       "550e8400-e29b-41d4-a716-446655440000",
  "IsDeepfake":               true,
  "CnnConfidence":            0.8756,
  "ElaScore":                 0.6234,
  "FftAnomalyScore":          0.7123,
  "ExifHasMetadata":          false,
  "ExifCameraInfo":           null,
  "ExifSuspiciousIndicators": "EXIF verisi yok;Küçük dosya boyutu",
  "GradcamImage":             "<base64 JPEG>",
  "ElaImage":                 "<base64 JPEG>",
  "FftImage":                 "<base64 JPEG>",
  "ThumbnailImage":           "<base64 JPEG>",
  "ProcessingTimeSeconds":    3.45,
  "Status":                   "Completed"
}
```

---

## 🧪 Swagger UI

```
http://localhost:8000/docs
```

`DEEPFAKE_API_KEY_DISABLED=true` iken Swagger'dan direkt test edilebilir.  
Key aktifken sağ üstteki **Authorize** butonuna key girin.

---

## ⚡ Benchmark

```bash
# Sunucu çalışıyor olmalı
uvicorn app.main:app --reload --port 8000

# macOS
python3 benchmark.py

# Windows
python benchmark.py

# Özel parametreler
python3 benchmark.py --url https://example.com/photo.jpg --n 10 --key my-secret-key
```

### Örnek Çıktı

```
✅ API çalışıyor  |  API Key: 🔓 KAPALI

  ROUTE BAZLI BENCHMARK
  /api/model       1.21s  ✅
  /api/ela         0.98s  ✅
  /api/fft         0.87s  ✅
  /api/metadata    0.12s  ✅
  /api/analyze     1.34s  ✅

  /api/analyze  –  5 istek
  İstek 1: 1.34s  ✅  HTTP 200
  İstek 2: 1.28s  ✅  HTTP 200
  İstek 3: 1.31s  ✅  HTTP 200
  İstek 4: 1.29s  ✅  HTTP 200
  İstek 5: 1.33s  ✅  HTTP 200

  Ortalama : 1.31s
  En Hızlı : 1.28s
  En Yavaş : 1.34s
```

---

## 🧠 Teknik Notlar

- **Disk yazımı yok** → görseller `base64 JPEG` olarak yanıtta taşınır
- **Paralel işleme** → `ThreadPoolExecutor` (Mac'te ProcessPool'dan daha hızlı)
- **ID yönetimi** → UUID her zaman .NET tarafından gelir, Python üretmez
- **API Key** → `X-API-Key` header, middleware seviyesinde kontrol edilir
- **Python 3.10 / 3.11** önerilir

### Analiz Yöntemleri

| Yöntem   | Amaç                            |
|----------|---------------------------------|
| CNN      | ResNet50 tabanlı sınıflandırma (simüle) |
| Grad-CAM | Model odak bölgelerini görselleştirir |
| ELA      | JPEG manipülasyon tespiti       |
| FFT      | Frekans alanı anomali tespiti   |
| Metadata | EXIF / dosya bilgisi analizi    |




🐳 Docker ile Çalıştırma

📦 1️⃣ Dockerfile ve .dockerignore

Proje kök dizininde şu dosyalar olmalıdır:

DeepFake-python/
├── Dockerfile
├── .dockerignore


⸻

🏗 2️⃣ Image Build

Proje klasöründe:

docker build -t deepfake-api .


⸻

▶️ 3️⃣ Container Çalıştırma

docker run --env-file .env -p 8000:8000 deepfake-api

API:

http://localhost:8000

Swagger:

http://localhost:8000/docs


⸻

🔐 Environment Variable ile Çalıştırma (Production)

docker run \
  -e DEEPFAKE_API_KEY_DISABLED=false \
  -e DEEPFAKE_API_KEY=super-secret-key \
  -p 8000:8000 \
  deepfake-api


⸻

🛑 Container Durdurma

docker ps
docker stop <container_id>


⸻

📦 Notlar
	•	Disk yazımı yok → servis stateless çalışır
	•	Volume gerekmez
	•	Production ortamında .env dosyası image içine eklenmez
	•	Python 3.11 slim base image kullanılır


