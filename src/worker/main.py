"""
Worker: Main (Composition Root)
================================
Tüm bağımlılıklar burada birleştirilir ve enjekte edilir.
Bu dosya dışında hiçbir yerde somut sınıf oluşturulmaz.

Tasarım notu:
  RabbitMQ bağlantısı her koptuğunda yeniden kurulur.
  Publisher, consumer ile aynı channel'ı paylaşır.
  Bu yüzden her yeniden bağlantıda use_case yeniden oluşturulur;
  servisler stateless olduğundan maliyet sıfırdır.

Başlatma:
    python -m src.worker.main
"""
from __future__ import annotations

import json
import logging
import multiprocessing
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from pika.exceptions import AMQPConnectionError

from src.application.use_cases.analyze_image_use_case import AnalyzeImageUseCase
from src.infrastructure.analysis.ela_service import ElaService
from src.infrastructure.analysis.fft_service import FftService
from src.infrastructure.analysis.metadata_service import MetadataService
from src.infrastructure.analysis.model_service import ModelService
from src.infrastructure.http.http_image_downloader import HttpImageDownloader
from src.infrastructure.messaging.rabbitmq import (
    RabbitMQPublisher,
    _build_params,
    _connect_with_retry,
)
from src.infrastructure.orchestrator.parallel_analysis_orchestrator import (
    ParallelAnalysisOrchestrator,
)
from src.worker.config import Config

# ── Loglama ───────────────────────────────────────────────────────
logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
    stream  = sys.stdout,
)
log = logging.getLogger("worker.main")

_shutdown = False


# ══════════════════════════════════════════════════════════════════
# GRACEFUL SHUTDOWN
# ══════════════════════════════════════════════════════════════════

def _register_signals(pool: ThreadPoolExecutor) -> None:
    def _handler(sig, frame):
        global _shutdown
        log.info("Sinyal alındı (%s) — kapatılıyor...", sig)
        _shutdown = True
        pool.shutdown(wait=False)

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT,  _handler)


# ══════════════════════════════════════════════════════════════════
# COMPOSITION ROOT
# ══════════════════════════════════════════════════════════════════

def _build_use_case(channel, cfg: Config, pool: ThreadPoolExecutor) -> AnalyzeImageUseCase:
    """
    Her yeni bağlantıda taze publisher ile use_case oluşturur.
    Analiz servisleri stateless — her seferinde oluşturmak maliyetsizdir.
    """
    return AnalyzeImageUseCase(
        downloader   = HttpImageDownloader(),
        orchestrator = ParallelAnalysisOrchestrator(
            ela_service      = ElaService(),
            fft_service      = FftService(),
            metadata_service = MetadataService(),
            model_service    = ModelService(),
            thread_pool      = pool,
        ),
        publisher    = RabbitMQPublisher(channel),
        result_queue = cfg.result_queue,
    )


# ══════════════════════════════════════════════════════════════════
# ANA DÖNGÜ
# ══════════════════════════════════════════════════════════════════

def main() -> None:
    global _shutdown

    cfg = Config.from_env()
    cpu = multiprocessing.cpu_count()

    log.info("═══════════════════════════════════════════════")
    log.info("  DeepFake Python Worker  v3.0 (Clean Arch)  ")
    log.info("  CPU       : %d çekirdek", cpu)
    log.info("  Threads   : %d", cfg.worker_threads)
    log.info("  RabbitMQ  : %s:%d", cfg.rabbitmq_host, cfg.rabbitmq_port)
    log.info("  Consume   : %s", cfg.analysis_queue)
    log.info("  Publish   : %s", cfg.result_queue)
    log.info("═══════════════════════════════════════════════")

    pool   = ThreadPoolExecutor(max_workers=cfg.worker_threads, thread_name_prefix="analysis")
    params = _build_params(
        cfg.rabbitmq_host, cfg.rabbitmq_port,
        cfg.rabbitmq_user, cfg.rabbitmq_pass,
        cfg.rabbitmq_url,
    )
    _register_signals(pool)

    while not _shutdown:
        connection = None
        try:
            connection = _connect_with_retry(params)
            channel    = connection.channel()

            channel.queue_declare(queue=cfg.analysis_queue, durable=True)
            channel.queue_declare(queue=cfg.result_queue,   durable=True)
            channel.basic_qos(prefetch_count=1)

            use_case = _build_use_case(channel, cfg, pool)

            def _on_message(ch, method, properties, body):
                try:
                    use_case.execute(json.loads(body))
                except json.JSONDecodeError as exc:
                    log.error("JSON parse hatası: %s", exc)
                finally:
                    ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_consume(queue=cfg.analysis_queue, on_message_callback=_on_message)
            log.info("[*] Dinleniyor → '%s'  |  CTRL+C ile dur", cfg.analysis_queue)
            channel.start_consuming()

        except (AMQPConnectionError, Exception) as err:
            if _shutdown:
                break
            log.error("Bağlantı hatası: %s. 5s sonra yeniden deneniyor...", err)
            time.sleep(5)

        finally:
            if connection and not connection.is_closed:
                try:
                    connection.close()
                except Exception:
                    pass

    log.info("ThreadPool kapatılıyor...")
    pool.shutdown(wait=True)
    log.info("Worker durduruldu.")


if __name__ == "__main__":
    main()
