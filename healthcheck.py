"""
healthcheck.py — RabbitMQ Worker Health Check
==============================================
Docker HEALTHCHECK komutu tarafından çalıştırılır:
  HEALTHCHECK CMD python healthcheck.py

Kontrol sırası:
  1. RabbitMQ'ya bağlan (5s timeout)
  2. analysis_queue var mı ve durable mi?
  3. result_queue var mı ve durable mi?

Çıkış kodları:
  0 → Sağlıklı  (healthy)
  1 → Hata      (unhealthy)
"""

import os
import sys
import socket
import pika
from pika.exceptions import AMQPConnectionError

# ── Konfigürasyon ─────────────────────────────────────────────────
RABBITMQ_HOST   = os.getenv("RABBITMQ_HOST",  "localhost")
RABBITMQ_PORT   = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER   = os.getenv("RABBITMQ_USER",  "admin")
RABBITMQ_PASS   = os.getenv("RABBITMQ_PASS",  "admin123")

REQUIRED_QUEUES = ["analysis_queue", "result_queue"]
CONNECT_TIMEOUT = 5   # saniye — bu sürede bağlanamazsa unhealthy


def check() -> tuple[bool, str]:
    """
    Tüm kontrolleri yapar.
    Returns: (başarılı_mı, açıklama_mesajı)
    """

    # ── 1. TCP erişilebilirlik (en hızlı kontrol) ─────────────────
    try:
        sock = socket.create_connection((RABBITMQ_HOST, RABBITMQ_PORT), timeout=CONNECT_TIMEOUT)
        sock.close()
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        return False, f"TCP bağlantısı başarısız ({RABBITMQ_HOST}:{RABBITMQ_PORT}): {e}"

    # ── 2. AMQP bağlantısı ────────────────────────────────────────
    connection = None
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                credentials=pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS),
                # Timeout: bu kadar sürede bağlanamazsa exception fırlat
                socket_timeout=CONNECT_TIMEOUT,
                connection_attempts=1,
                retry_delay=0,
            )
        )
        channel = connection.channel()

    except AMQPConnectionError as e:
        return False, f"AMQP bağlantısı başarısız: {e}"
    except Exception as e:
        return False, f"Beklenmeyen bağlantı hatası: {e}"

    # ── 3. Queue varlık ve durable kontrolü ───────────────────────
    try:
        for queue_name in REQUIRED_QUEUES:
            # passive=True → queue yoksa exception fırlatır, oluşturmaz
            channel.queue_declare(queue=queue_name, durable=True, passive=True)

    except Exception as e:
        return False, f"Queue kontrolü başarısız ('{queue_name}'): {e}"

    finally:
        if connection and not connection.is_closed:
            try:
                connection.close()
            except Exception:
                pass

    return True, f"OK — RabbitMQ bağlı, queue'lar hazır: {', '.join(REQUIRED_QUEUES)}"


# ── Ana çalışma ───────────────────────────────────────────────────
if __name__ == "__main__":
    healthy, message = check()

    if healthy:
        print(f"[HEALTHY] {message}")
        sys.exit(0)
    else:
        print(f"[UNHEALTHY] {message}", file=sys.stderr)
        sys.exit(1)