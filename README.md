# DeepFake Detection – Python Worker

**Stack:** Python 3.11 · RabbitMQ 3.13 · Docker Compose  
**Versiyon:** 3.0.0 | **Mimari:** Clean Architecture (Async Event-Driven)

---

## Genel Bakış

Bu servis, `.NET Web API`'nin `analysis_queue`'ya koyduğu görevleri tüketir, dört analiz modülünü paralel çalıştırır ve sonuçları `result_queue`'ya yayınlar. HTTP sunucusu içermez — yalnızca RabbitMQ tabanlı asenkron worker'dır.

```
.NET Web API
    │
    │  analysis_queue'ya publish (JSON)
    ▼
┌─────────────────────┐
│      RabbitMQ        │
│  ┌───────────────┐  │
│  │analysis_queue │  │
│  └──────┬────────┘  │
│         │           │
│  ┌──────▼────────┐  │
│  │ result_queue  │  │
│  └───────────────┘  │
└─────────────────────┘
    ↑ consume / publish ↓
┌─────────────────────────────────────┐
│         Python Worker               │
│                                     │
│  AnalyzeImageUseCase                │
│    ├── HttpImageDownloader          │
│    ├── ParallelAnalysisOrchestrator │
│    │     ├── ElaService             │
│    │     ├── FftService             │
│    │     ├── MetadataService        │
│    │     └── ModelService           │
│    └── RabbitMQPublisher            │
└─────────────────────────────────────┘
    │
    ▼  result_queue'dan consume
┌─────────────────────┐
│ .NET BackgroundSvc   │
│  DB: Status=Completed│
└─────────────────────┘
```

---

## Proje Yapısı (Clean Architecture)

```
deepfake-worker/
│
├── src/
│   │
│   ├── domain/                         ← İÇ KATMAN (hiçbir dışa bağımlılık yok)
│   │   ├── entities/
│   │   │   ├── analysis_request.py     ← Gelen mesaj entity'si
│   │   │   └── analysis_result.py      ← Çıkış entity'leri + AnalysisStatus enum
│   │   └── interfaces/
│   │       └── __init__.py             ← Tüm soyut sözleşmeler (ABC)
│   │
│   ├── application/                    ← İŞ KURALLARI KATMANI
│   │   └── use_cases/
│   │       └── analyze_image_use_case.py  ← Uçtan uca akışı yönetir
│   │
│   ├── infrastructure/                 ← DIŞ KATMAN (somut implementasyonlar)
│   │   ├── analysis/
│   │   │   ├── ela_service.py          ← ELA analizi
│   │   │   ├── fft_service.py          ← FFT analizi
│   │   │   ├── metadata_service.py     ← EXIF analizi
│   │   │   └── model_service.py        ← CNN simülasyonu + Grad-CAM
│   │   ├── http/
│   │   │   └── http_image_downloader.py  ← URL'den görsel indirir
│   │   ├── messaging/
│   │   │   └── rabbitmq.py             ← Consumer + Publisher (pika)
│   │   └── orchestrator/
│   │       └── parallel_analysis_orchestrator.py  ← ThreadPool paralel çalıştırıcı
│   │
│   └── worker/                         ← GİRİŞ NOKTASI (Composition Root)
│       ├── config.py                   ← Env değişkenlerini tek noktada toplar
│       └── main.py                     ← DI bağlama + ana döngü
│
├── benchmark.py                        ← RabbitMQ üzerinden performans testi
├── healthcheck.py                      ← Docker HEALTHCHECK scripti
├── Dockerfile                          ← Multi-stage build
├── docker-compose.yml                  ← RabbitMQ + python-worker
├── requirements.txt                    ← Minimal bağımlılıklar
└── .env                                ← Ortam değişkenleri (örnek aşağıda)
```

### Bağımlılık Kuralı

```
Worker/Main → Application → Domain ← Infrastructure
```

- **Domain** hiçbir dış pakete bağımlı değildir.  
- **Application** yalnızca domain'e bağımlıdır.  
- **Infrastructure** domain arayüzlerini implemente eder.  
- **Worker/Main** (Composition Root) hepsini bir araya getirir.

---

## Kurulum

### Gereksinimler

| Araç        | Versiyon |
|-------------|----------|
| Docker      | 24+      |
| Python      | 3.11+    |
| RabbitMQ    | 3.13     |

### Python Bağımlılıkları

```txt
pillow>=10.3.0
numpy==1.26.3
opencv-python==4.9.0.80
requests==2.31.0
pika==1.3.2
python-dotenv==1.0.0
```

### .NET NuGet

```bash
dotnet add package RabbitMQ.Client --version 6.8.1
dotnet add package Microsoft.Extensions.Hosting
```

---

## Çalıştırma

### Docker Compose (Önerilen)

```bash
# 1. Projeyi klonla
git clone https://github.com/cihanoren/DeepFake-python.git
cd DeepFake-python

# 2. Ortam dosyasını oluştur
cp .env.example .env

# 3. Build & başlat
docker-compose up -d --build

# 4. Servisleri kontrol et
docker-compose ps

# 5. Worker loglarını izle
docker-compose logs -f python-worker

# 6. RabbitMQ Yönetim UI
# http://localhost:15672  →  admin / admin123

# Durdur
docker-compose down
```

### Yerel Geliştirme

```bash
pip install -r requirements.txt

# RabbitMQ (sadece bu servis)
docker-compose up -d rabbitmq

# Worker'ı başlat
python -m src.worker.main
```

---

## .env Dosyası

```env
# RabbitMQ
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=admin
RABBITMQ_PASS=admin123

# Kuyruk isimleri (opsiyonel, varsayılanlar mevcut)
ANALYSIS_QUEUE=analysis_queue
RESULT_QUEUE=result_queue

# Worker
WORKER_THREADS=4

# Railway / CloudAMQP (varsa RABBITMQ_HOST/PORT'u ezer)
# RABBITMQ_URL=amqps://user:pass@host/vhost

# .NET için
# DB_CONNECTION=Server=...;Database=DeepFakeDb;
```

---

## Mesaj Formatı

### analysis_queue → Python Worker (Gelen)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "image_url": "https://api.example.com/uploads/img123.jpg"
}
```

### result_queue → .NET BackgroundSvc (Çıkan — Başarı)

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
  "ElaImageBase64":     "<base64 JPEG>",
  "FftImageBase64":     "<base64 JPEG>",
  "ProcessingTimeSeconds": 1.87,
  "Status": "Completed",
  "ErrorMessage": null
}
```

### result_queue → .NET (Çıkan — Hata)

```json
{
  "Id": "550e8400-e29b-41d4-a716-446655440000",
  "Status": "Failed",
  "ErrorMessage": "Görsel indirilemedi: 404 Not Found"
}
```

---

## Test

### 1. RabbitMQ UI'dan Manuel Test

`http://localhost:15672` → **Queues** → `analysis_queue` → **Publish message**:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "image_url": "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEgI8hbyGkUDAF7hItsu4gTbLgrcM7YJLvTEL494jT4TR_fK3YKb9FRiWd0ZZOWUFFB20ZsAkGAYDvcxR5d9WC7WTy29BnOCobwqhNlfSaDjam8POajCwHVRIJaC9pitYr9Zu1x4h30uWEbE/s1600/The_Last_Supper_Jacopo_Bassano_1542.jpg"
}
```

### 2. Beklenen Worker Log Çıktısı

```
2024-01-15 10:23:01 [INFO] worker.main – [*] Dinleniyor → 'analysis_queue'
2024-01-15 10:23:05 [INFO] use_case.analyze_image – ▶ Yeni görev | ID: 550e8400-...
2024-01-15 10:23:05 [INFO] use_case.analyze_image –   ↓ İndiriliyor: https://...
2024-01-15 10:23:06 [INFO] orchestrator.parallel –   ⚡ Paralel analiz başlatıldı (4 thread)...
2024-01-15 10:23:06 [INFO] orchestrator.parallel –   ✓ FFT tamamlandı
2024-01-15 10:23:06 [INFO] orchestrator.parallel –   ✓ META tamamlandı
2024-01-15 10:23:07 [INFO] orchestrator.parallel –   ✓ ELA tamamlandı
2024-01-15 10:23:07 [INFO] orchestrator.parallel –   ✓ MODEL tamamlandı
2024-01-15 10:23:07 [INFO] use_case.analyze_image – ✔ Tamamlandı | ID: 550e8400-... | Süre: 2.1s
```

### 3. Benchmark

```bash
python benchmark.py --n 5
```

### 4. Yatay Ölçeklendirme

```bash
# 3 worker paralel çalışır; RabbitMQ yükü otomatik dağıtır
docker-compose up --scale python-worker=3 -d
```

---

## Production Önerileri

### Dead Letter Queue (DLX)

```python
channel.queue_declare(
    queue     = "analysis_queue",
    durable   = True,
    arguments = {
        "x-dead-letter-exchange":    "dlx.direct",
        "x-dead-letter-routing-key": "analysis.failed",
        "x-message-ttl":             86_400_000,  # 24 saat
    },
)
```

### Idempotency (.NET tarafı)

```sql
UPDATE AnalysisResults
SET    Status = 'Completed', ...
WHERE  Id = @Id AND Status = 'Processing'
-- Yalnızca 'Processing' durumdayken güncelle
```

### Retry Header

```python
retry_count = int(properties.headers.get("x-retry-count", 0))
if retry_count >= 3:
    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    return
```

---

## Hata Giderme

```bash
# Queue durumu
docker exec deepfake-rabbitmq rabbitmqctl list_queues name messages consumers

# Worker logları
docker-compose logs -f python-worker

# Worker yeniden başlat
docker-compose restart python-worker

# Temizlik
docker-compose down -v && docker system prune -a
```

---

## İletişim

**Proje Sahipleri:** [alikorogluts](https://github.com/alikorogluts) · [cihanoren](https://github.com/cihanoren)  
**Sorun Bildirme:** [GitHub Issues](https://github.com/cihanoren/DeepFake-python/issues)
