# DeepFake Detection – Async Event-Driven Mimari

**Stack:** Python · RabbitMQ · .NET 8 · Docker Compose
**Versiyon:** 3.2.0 | **Python:** 3.11 | **RabbitMQ:** 3.13

---

## Sistem Akışı

```
Kullanıcı
   │
   │  POST /api/analysis/upload
   ▼
┌─────────────────────┐
│   .NET 8 Web API    │
│  1. Görseli diske   │
│  2. DB: Processing  │
│  3. Publish ──────────────────────────────────────────┐
└─────────────────────┘                                 │
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
                                               consume ↑  ↓ publish
                                            ┌─────────────────────┐
                                            │   Python Worker      │
                                            │  ThreadPoolExecutor  │
                                            │  CNN │ ELA │ FFT │ META
                                            │   (paralel ~1.3s)   │
                                            └─────────────────────┘
                                                        │ consume
                                            ┌─────────────────────┐
                                            │ .NET BackgroundSvc   │
                                            │  4. Base64 → Disk   │
                                            │  5. DB: Completed   │
                                            └─────────────────────┘
```

---

## Proje Yapısı

```
DeepFake-python/
│
├── worker.py                      ← RabbitMQ Worker (YENİ v2.1)
├── Dockerfile                     ← MODE=api | MODE=worker desteği (GÜNCELLENDİ)
├── docker-compose.yml             ← RabbitMQ + python-worker (GÜNCELLENDİ)
├── requirements.txt               ← pika zaten dahil
├── .env                           ← ortam değişkenleri
│
├── app/
│   ├── __init__.py
│   ├── main.py                    ← FastAPI (HTTP mod için)
│   └── models.py
│
├── analysis/
│   ├── __init__.py
│   ├── error_level_analysis.py    ← ELA
│   ├── fast_fourier_transform.py  ← FFT
│   ├── metadata_analyzer.py       ← EXIF
│   └── model_simulator.py         ← CNN + Grad-CAM
│
└── DeepFakeApi/                   ← .NET projesi
    ├── Program.cs                 ← DI kayıtları
    └── Infrastructure/Messaging/
        ├── RabbitMqPublisher.cs   ← analysis_queue'ya publish
        └── AnalysisResultConsumer.cs ← result_queue'yu dinler
```

---

## Gerekli Paketler

### Python – requirements.txt (zaten mevcut)

```txt
pika==1.3.2          # RabbitMQ client
requests==2.31.0
fastapi==0.109.0
uvicorn[standard]==0.27.0
httpx==0.26.0
pillow>=10.3.0
numpy==1.26.3
opencv-python==4.9.0.80
pydantic==2.5.3
python-dotenv==1.0.0
```

### .NET – NuGet

```bash
dotnet add package RabbitMQ.Client --version 6.8.1
dotnet add package Microsoft.Extensions.Hosting
```

---

## .env Dosyası

```env
# RabbitMQ
RABBITMQ_USER=admin
RABBITMQ_PASS=admin123

# Python Worker
WORKER_THREADS=4

# FastAPI (HTTP mod)
DEEPFAKE_API_KEY=change-me-in-production
DEEPFAKE_API_KEY_DISABLED=false

# .NET (gerekirse)
DB_CONNECTION=Server=...;Database=DeepFakeDb;
```

---

## Dockerfile – MODE Değişkeni

Aynı image hem API hem worker olarak çalışır:

```bash
# FastAPI modu (varsayılan)
docker run -e MODE=api deepfake-worker:latest

# RabbitMQ Worker modu
docker run -e MODE=worker deepfake-worker:latest
```

docker-compose.yml'de `python-worker` servisi `MODE=worker` ile çalışır.

---

## Çalıştırma

```bash
# 1. Projeyi klonla
git clone https://github.com/cihanoren/DeepFake-python.git
cd DeepFake-python

# 2. .env oluştur
cp .env.example .env

# 3. Build & başlat
docker-compose up -d --build

# 4. Servisleri kontrol et
docker-compose ps

# 5. Logları izle
docker-compose logs -f python-worker

# 6. RabbitMQ Yönetim UI
# http://localhost:15672  →  admin / admin123

# Durdur
docker-compose down
```

---

## Test Senaryosu

### 1. RabbitMQ UI'dan Manuel Test

http://localhost:15672 → Queues → `analysis_queue` → Publish message:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "image_url": "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEgI8hbyGkUDAF7hItsu4gTbLgrcM7YJLvTEL494jT4TR_fK3YKb9FRiWd0ZZOWUFFB20ZsAkGAYDvcxR5d9WC7WTy29BnOCobwqhNlfSaDjam8POajCwHVRIJaC9pitYr9Zu1x4h30uWEbE/s1600/The_Last_Supper_Jacopo_Bassano_1542.jpg",
  "original_image_path": "uploads/test.jpg"
}
```

### 2. Beklenen Worker Log Çıktısı

```
2024-01-15 10:23:01 [INFO] ▶ Yeni görev | ID: 550e8400-...
2024-01-15 10:23:01 [INFO]   ↓ İndiriliyor: https://blogger.googl...
2024-01-15 10:23:02 [INFO]   ⚡ Paralel analiz (4 thread)...
2024-01-15 10:23:02 [INFO]   ✓ FFT tamamlandı
2024-01-15 10:23:02 [INFO]   ✓ META tamamlandı
2024-01-15 10:23:03 [INFO]   ✓ ELA tamamlandı
2024-01-15 10:23:03 [INFO]   ✓ MODEL tamamlandı
2024-01-15 10:23:03 [INFO] ✔ Tamamlandı | ID: 550e8400-... | Süre: 2.1s
```

### 3. result_queue Kontrol

http://localhost:15672 → Queues → `result_queue` → Get messages

### 4. .NET Upload Endpoint

```bash
curl -X POST http://localhost:5000/api/analysis/upload \
  -F "file=@test.jpg"
# → { "id": "...", "status": "Processing" }

# Birkaç saniye sonra:
curl http://localhost:5000/api/analysis/{id}/status
# → { "id": "...", "status": "Completed", "isDeepfake": true, ... }
```

### 5. Yatay Ölçeklendirme Testi

```bash
# 3 worker aynı anda çalışır; RabbitMQ yükü otomatik dağıtır
docker-compose up --scale python-worker=3 -d
```

---

## Worker vs FastAPI Karşılaştırması

| Özellik              | FastAPI (HTTP)          | RabbitMQ Worker (Async)        |
|----------------------|-------------------------|--------------------------------|
| Tetikleyici          | HTTP POST               | Kuyruk mesajı                  |
| Bağlantı             | .NET bekler (sync)      | .NET beklemez (async)          |
| Timeout riski        | Yüksek (60s limit)      | Yok                            |
| Yeniden deneme       | Manuel retry gerekir    | RabbitMQ otomatik              |
| Ölçeklendirme        | Uvicorn workers         | `--scale python-worker=N`      |
| Hata yönetimi        | HTTP 500 dönebilir      | DLQ'ya düşer, kaybolmaz        |
| Kullanım durumu      | Test, geliştirme        | **Production önerilen**        |

---

## Production Önerileri

### Dead Letter Queue (DLX) – Hatalı mesajları koru

```python
channel.queue_declare(
    queue=ANALYSIS_QUEUE,
    durable=True,
    arguments={
        "x-dead-letter-exchange": "dlx.direct",
        "x-dead-letter-routing-key": "analysis.failed",
        "x-message-ttl": 86400000,   # 24 saat TTL
    }
)
```

### Idempotency – Aynı ID iki kez gelirse DB bozulmasın

```sql
-- EF Core'da:
UPDATE AnalysisResults
SET    Status = 'Completed', ...
WHERE  Id = @Id AND Status = 'Processing'
-- Sadece Processing durumdayken güncelle
```

### Retry Header ile Yeniden Deneme

```python
retry_count = int(properties.headers.get("x-retry-count", 0))
if retry_count >= 3:
    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    return
# hata sonrası:
ch.basic_publish(
    exchange='', routing_key=ANALYSIS_QUEUE, body=body,
    properties=pika.BasicProperties(
        delivery_mode=2,
        headers={"x-retry-count": retry_count + 1}
    )
)
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

# Tüm container durum
docker-compose ps

# Temizlik
docker-compose down -v && docker system prune -a
```

---

## İletişim

**Proje Sahipleri:** [alikorogluts](https://github.com/alikorogluts) · [cihanoren](https://github.com/cihanoren)

**Sorun Bildirme:** [GitHub Issues](https://github.com/cihanoren/DeepFake-python/issues)