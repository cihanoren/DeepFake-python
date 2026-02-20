"""
DeepFake Python Worker  v2.1  –  RabbitMQ Async Worker
=======================================================
Gerçek analysis/ modüllerini kullanır:
  analyze_ela, analyze_fft, analyze_metadata, simulate_model_prediction

Mimari:
  analysis_queue → consume → ThreadPool paralel analiz → result_queue publish

Yeni özellikler (v1 → v2):
  ✅ Gerçek analysis/ modüllerine entegrasyon
  ✅ CPU sayısına göre ThreadPoolExecutor (as_completed ile paralel)
  ✅ RABBITMQ_USER/PASS ortam değişkeni (docker-compose auth)
  ✅ Exponential backoff bağlantı retry (3s→6s→12s→max 30s)
  ✅ Bağlantı kopunca worker ölmez, otomatik yeniden bağlanır
  ✅ Hata durumunda result_queue'ya Failed payload gönderilir
  ✅ SIGTERM/SIGINT ile graceful shutdown
"""

import os
import json
import time
import signal
import logging
import requests
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed

import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError

# ── Gerçek analiz modülleri (analysis/ paketi) ────────────────────
from analysis import (
    analyze_ela,
    analyze_fft,
    analyze_metadata,
    simulate_model_prediction,
)

# ── Loglama ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("deepfake-worker")

# ── Konfigürasyon ─────────────────────────────────────────────────
RABBITMQ_HOST  = os.getenv("RABBITMQ_HOST",  "localhost")
RABBITMQ_PORT  = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER  = os.getenv("RABBITMQ_USER",  "admin")
RABBITMQ_PASS  = os.getenv("RABBITMQ_PASS",  "admin123")

ANALYSIS_QUEUE = "analysis_queue"
RESULT_QUEUE   = "result_queue"

# CPU'ya göre pool boyutu (env override mümkün)
_CPU           = multiprocessing.cpu_count()
WORKER_THREADS = int(os.getenv("WORKER_THREADS", str(min(_CPU * 2, 16))))

# Thread pool — tüm analizler burada paralel çalışır
_POOL = ThreadPoolExecutor(max_workers=WORKER_THREADS, thread_name_prefix="analysis")

log.info(f"CPU: {_CPU} çekirdek  |  ThreadPool: {WORKER_THREADS} worker")

# ── Graceful Shutdown ─────────────────────────────────────────────
_shutdown = False

def _handle_signal(sig, frame):
    global _shutdown
    log.info(f"Sinyal alındı ({sig}), worker kapatılıyor...")
    _shutdown = True

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT,  _handle_signal)


# ══════════════════════════════════════════════════════════════════
# GÖRSEL İNDİRME
# ══════════════════════════════════════════════════════════════════

def download_image(url: str) -> bytes:
    """Görseli URL'den indirir."""
    log.info(f"  ↓ İndiriliyor: {url[:90]}...")
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.content


# ══════════════════════════════════════════════════════════════════
# PARALEL ANALİZ
# ══════════════════════════════════════════════════════════════════

def run_parallel_analysis(image_bytes: bytes, filename: str) -> dict:
    """
    4 analiz fonksiyonunu ThreadPool ile aynı anda başlatır.
    Toplam süre ≈ en yavaş analizin süresi (~1.2s), seri değil (~3.2s).
    """
    futures = {
        _POOL.submit(simulate_model_prediction, image_bytes):           "model",
        _POOL.submit(analyze_ela,               image_bytes):           "ela",
        _POOL.submit(analyze_fft,               image_bytes):           "fft",
        _POOL.submit(analyze_metadata,          image_bytes, filename): "meta",
    }

    results = {}
    for future in as_completed(futures):
        name = futures[future]
        try:
            results[name] = future.result()
            log.info(f"  ✓ {name.upper()} tamamlandı")
        except Exception as exc:
            log.error(f"  ✗ {name.upper()} hatası: {exc}", exc_info=True)
            raise RuntimeError(f"{name} analizi başarısız: {exc}") from exc

    return results


# ══════════════════════════════════════════════════════════════════
# MESAJ İŞLEYİCİ
# ══════════════════════════════════════════════════════════════════

def process_message(ch, method, properties, body):
    """
    analysis_queue'dan gelen her mesaj için tetiklenir.
    İş bitince result_queue'ya sonucu publish eder.
    Her halükarda ACK gönderir (mesaj kuyruktan silinir).
    """
    data = {}
    try:
        # 1. JSON parse
        data      = json.loads(body)
        record_id = data.get("id")
        image_url = data.get("image_url")

        log.info(f"▶ Yeni görev | ID: {record_id}")
        start_time = time.time()

        # 2. Görsel indir
        image_bytes = download_image(image_url)
        filename    = image_url.split("/")[-1].split("?")[0] or "image.jpg"

        # 3. Paralel analiz (gerçek modüller)
        log.info(f"  ⚡ Paralel analiz ({WORKER_THREADS} thread)...")
        res = run_parallel_analysis(image_bytes, filename)

        model_r = res["model"]
        ela_r   = res["ela"]
        fft_r   = res["fft"]
        meta_r  = res["meta"]

        elapsed = round(time.time() - start_time, 2)

        # 4. Sonuç paketi — .NET AnalysisResult DB modeli ile birebir eşleşir
        result_payload = {
            "Id":                      record_id,
            "IsDeepfake":              model_r["is_deepfake"],
            "CnnConfidence":           model_r["confidence"],
            "ElaScore":                ela_r["score"],
            "FftAnomalyScore":         fft_r["anomaly_score"],
            "ExifHasMetadata":         meta_r["has_metadata"],
            "ExifCameraInfo":          meta_r["camera_info"],
            "ExifSuspiciousIndicators": (
                ";".join(meta_r["suspicious_indicators"])
                if meta_r["suspicious_indicators"] else None
            ),
            "GradcamImageBase64": model_r["gradcam_b64"],
            "ElaImageBase64":     ela_r["heatmap_b64"],
            "FftImageBase64":     fft_r["spectrum_b64"],
            "ProcessingTimeSeconds": elapsed,
            "Status":       "Completed",
            "ErrorMessage": None,
        }

        # 5. result_queue'ya publish et
        ch.basic_publish(
            exchange='',
            routing_key=RESULT_QUEUE,
            body=json.dumps(result_payload),
            properties=pika.BasicProperties(
                delivery_mode=2,                 # Durable — disk'e yaz
                content_type="application/json",
            ),
        )
        log.info(f"✔ Tamamlandı | ID: {record_id} | Süre: {elapsed}s")

    except Exception as exc:
        log.error(f"✘ Hata | ID: {data.get('id', '?')} | {exc}", exc_info=True)

        # DB'de 'Processing' askıda kalmasın diye .NET'i bilgilendir
        error_payload = {
            "Id":           data.get("id"),
            "Status":       "Failed",
            "ErrorMessage": str(exc),
        }
        try:
            ch.basic_publish(
                exchange='',
                routing_key=RESULT_QUEUE,
                body=json.dumps(error_payload),
                properties=pika.BasicProperties(delivery_mode=2),
            )
        except Exception as pub_exc:
            log.error(f"  Hata payload gönderilemedi: {pub_exc}")

    finally:
        # Her durumda ACK → mesaj kuyruktan silinir, sıradaki alınır
        ch.basic_ack(delivery_tag=method.delivery_tag)


# ══════════════════════════════════════════════════════════════════
# BAĞLANTI — Exponential Backoff
# ══════════════════════════════════════════════════════════════════

def create_connection() -> pika.BlockingConnection:
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=60,
        blocked_connection_timeout=300,
    )

    delay = 3
    for attempt in range(1, 11):
        try:
            conn = pika.BlockingConnection(params)
            log.info(f"✔ RabbitMQ: {RABBITMQ_HOST}:{RABBITMQ_PORT}")
            return conn
        except AMQPConnectionError:
            log.warning(f"Bağlantı denemesi {attempt}/10 başarısız. {delay}s bekleniyor...")
            time.sleep(delay)
            delay = min(delay * 2, 30)

    raise RuntimeError("RabbitMQ'ya bağlanılamadı. 10 deneme tükendi.")


# ══════════════════════════════════════════════════════════════════
# ANA DÖNGÜ
# ══════════════════════════════════════════════════════════════════

def start_worker():
    global _shutdown

    log.info("═══════════════════════════════════════")
    log.info("  DeepFake Python Worker  v2.1")
    log.info(f"  RabbitMQ  : {RABBITMQ_HOST}:{RABBITMQ_PORT}")
    log.info(f"  Consume   : {ANALYSIS_QUEUE}")
    log.info(f"  Publish   : {RESULT_QUEUE}")
    log.info(f"  Threads   : {WORKER_THREADS}")
    log.info("═══════════════════════════════════════")

    while not _shutdown:
        connection = None
        try:
            connection = create_connection()
            channel    = connection.channel()

            # Durable queue — restart'ta mesajlar kaybolmaz
            channel.queue_declare(queue=ANALYSIS_QUEUE, durable=True)
            channel.queue_declare(queue=RESULT_QUEUE,   durable=True)

            # prefetch_count=1 → iş bitmeden yeni mesaj alma
            # (ThreadPool zaten içeride paralel çalışıyor, bu yeterli)
            channel.basic_qos(prefetch_count=1)

            channel.basic_consume(
                queue=ANALYSIS_QUEUE,
                on_message_callback=process_message,
            )

            log.info(f"[*] Dinleniyor → '{ANALYSIS_QUEUE}'  |  CTRL+C ile dur")
            channel.start_consuming()

        except (AMQPConnectionError, AMQPChannelError) as err:
            log.error(f"Bağlantı koptu: {err}. Yeniden bağlanılıyor...")
            time.sleep(5)

        except KeyboardInterrupt:
            _shutdown = True

        finally:
            if connection and not connection.is_closed:
                try:
                    connection.close()
                except Exception:
                    pass

    log.info("ThreadPool kapatılıyor...")
    _POOL.shutdown(wait=True)
    log.info("Worker durduruldu.")


if __name__ == "__main__":
    start_worker()