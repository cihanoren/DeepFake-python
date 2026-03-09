"""
healthcheck.py — RabbitMQ Worker Health Check
==============================================
Docker HEALTHCHECK komutu tarafından çalıştırılır.

Kontrol sırası:
  1. RabbitMQ TCP erişilebilirliği (5s timeout)
  2. AMQP bağlantısı (kimlik doğrulama)
  3. analysis_queue ve result_queue varlığı (passive declare)

Çıkış kodları:
  0 → Sağlıklı  (healthy)
  1 → Hata      (unhealthy)
"""
from __future__ import annotations

import os
import socket
import sys

import pika
from pika.exceptions import AMQPConnectionError

RABBITMQ_HOST   = os.getenv("RABBITMQ_HOST",  "localhost")
RABBITMQ_PORT   = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER   = os.getenv("RABBITMQ_USER",  "admin")
RABBITMQ_PASS   = os.getenv("RABBITMQ_PASS",  "admin123")
RABBITMQ_URL    = os.getenv("RABBITMQ_URL")

ANALYSIS_QUEUE  = os.getenv("ANALYSIS_QUEUE", "analysis_queue")
RESULT_QUEUE    = os.getenv("RESULT_QUEUE",   "result_queue")
REQUIRED_QUEUES = [ANALYSIS_QUEUE, RESULT_QUEUE]
CONNECT_TIMEOUT = 5


def check() -> tuple[bool, str]:
    # 1. TCP erişilebilirlik
    try:
        sock = socket.create_connection((RABBITMQ_HOST, RABBITMQ_PORT), timeout=CONNECT_TIMEOUT)
        sock.close()
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        return False, f"TCP bağlantısı başarısız ({RABBITMQ_HOST}:{RABBITMQ_PORT}): {e}"

    # 2. AMQP bağlantısı
    connection = None
    try:
        if RABBITMQ_URL:
            params = pika.URLParameters(RABBITMQ_URL)
        else:
            params = pika.ConnectionParameters(
                host            = RABBITMQ_HOST,
                port            = RABBITMQ_PORT,
                credentials     = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS),
                socket_timeout  = CONNECT_TIMEOUT,
                connection_attempts = 1,
                retry_delay     = 0,
            )

        connection = pika.BlockingConnection(params)
        channel    = connection.channel()

    except AMQPConnectionError as e:
        return False, f"AMQP bağlantısı başarısız: {e}"
    except Exception as e:
        return False, f"Beklenmeyen bağlantı hatası: {e}"

    # 3. Queue kontrol
    try:
        for queue_name in REQUIRED_QUEUES:
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


if __name__ == "__main__":
    healthy, message = check()
    if healthy:
        print(f"[HEALTHY] {message}")
        sys.exit(0)
    else:
        print(f"[UNHEALTHY] {message}", file=sys.stderr)
        sys.exit(1)
