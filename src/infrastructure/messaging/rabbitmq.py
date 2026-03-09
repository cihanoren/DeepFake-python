"""
Infrastructure: RabbitMQ Consumer & Publisher
==============================================
IMessageConsumer ve IMessagePublisher'ın pika tabanlı implementasyonları.

Özellikler:
  - Exponential backoff ile bağlantı yeniden deneme
  - Durable queue tanımlaması
  - prefetch_count=1 (mesaj işlenmeden bir sonraki alınmaz)
  - Her halükarda ACK (mesaj kuyrukta askıda kalmaz)
  - SIGTERM/SIGINT ile graceful shutdown
"""
from __future__ import annotations

import json
import logging
import time
from typing import Callable

import pika
from pika.exceptions import AMQPChannelError, AMQPConnectionError

from src.domain.interfaces import IMessageConsumer, IMessagePublisher, MessageHandler

log = logging.getLogger("infrastructure.rabbitmq")


# ── Bağlantı parametreleri ────────────────────────────────────────

def _build_params(
    host: str,
    port: int,
    user: str,
    password: str,
    url: str | None = None,
) -> pika.ConnectionParameters | pika.URLParameters:
    if url:
        log.info("AMQP URL kullanılıyor.")
        return pika.URLParameters(url)

    return pika.ConnectionParameters(
        host        = host,
        port        = port,
        credentials = pika.PlainCredentials(user, password),
        heartbeat   = 60,
        blocked_connection_timeout = 300,
    )


def _connect_with_retry(
    params,
    max_attempts: int = 10,
    base_delay:   int = 3,
) -> pika.BlockingConnection:
    delay = base_delay
    for attempt in range(1, max_attempts + 1):
        try:
            conn = pika.BlockingConnection(params)
            log.info("✔ RabbitMQ bağlantısı başarılı")
            return conn
        except AMQPConnectionError:
            log.warning(
                "Bağlantı denemesi %d/%d başarısız. %ds bekleniyor...",
                attempt, max_attempts, delay,
            )
            time.sleep(delay)
            delay = min(delay * 2, 30)

    raise RuntimeError("RabbitMQ'ya bağlanılamadı. Tüm denemeler tükendi.")


# ══════════════════════════════════════════════════════════════════
# PUBLISHER
# ══════════════════════════════════════════════════════════════════

class RabbitMQPublisher(IMessagePublisher):
    """
    Durable bir kuyruğa JSON mesaj yayınlar.
    Bağlantı nesnesi dışarıdan enjekte edilir (consumer ile paylaşılır).
    """

    def __init__(self, channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
        self._channel = channel

    def publish(self, queue_name: str, payload: dict) -> None:
        self._channel.basic_publish(
            exchange    = "",
            routing_key = queue_name,
            body        = json.dumps(payload),
            properties  = pika.BasicProperties(
                delivery_mode  = 2,                   # Durable — restart'ta kaybolmaz
                content_type   = "application/json",
            ),
        )
        log.debug("→ Yayınlandı: %s", queue_name)


# ══════════════════════════════════════════════════════════════════
# CONSUMER
# ══════════════════════════════════════════════════════════════════

class RabbitMQConsumer(IMessageConsumer):
    """
    Belirtilen kuyruktan mesaj tüketir.
    Her mesajı on_message callback'ine iletir, ardından ACK gönderir.
    Bağlantı kopunca otomatik yeniden bağlanır.
    """

    def __init__(
        self,
        host:     str,
        port:     int,
        user:     str,
        password: str,
        url:      str | None = None,
    ) -> None:
        self._params   = _build_params(host, port, user, password, url)
        self._shutdown = False

    def start_consuming(self, queue_name: str, on_message: MessageHandler) -> None:
        """Kuyruktan mesaj okumaya başlar. _shutdown=True olana dek çalışır."""

        while not self._shutdown:
            connection: pika.BlockingConnection | None = None
            try:
                connection = _connect_with_retry(self._params)
                channel    = connection.channel()

                channel.queue_declare(queue=queue_name, durable=True)
                channel.basic_qos(prefetch_count=1)

                def _callback(ch, method, properties, body):
                    try:
                        data = json.loads(body)
                        on_message(data)
                    except json.JSONDecodeError as exc:
                        log.error("JSON parse hatası: %s | body: %.200s", exc, body)
                    finally:
                        ch.basic_ack(delivery_tag=method.delivery_tag)

                channel.basic_consume(queue=queue_name, on_message_callback=_callback)
                log.info("[*] Dinleniyor → '%s'  |  CTRL+C ile dur", queue_name)
                channel.start_consuming()

            except (AMQPConnectionError, AMQPChannelError) as err:
                log.error("Bağlantı koptu: %s. Yeniden bağlanılıyor...", err)
                time.sleep(5)

            except KeyboardInterrupt:
                self._shutdown = True

            finally:
                if connection and not connection.is_closed:
                    try:
                        connection.close()
                    except Exception:
                        pass

    def stop(self) -> None:
        self._shutdown = True
        log.info("Consumer durdurma sinyali alındı.")
