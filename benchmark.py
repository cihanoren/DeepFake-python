"""
benchmark.py — RabbitMQ Worker Performans Testi
================================================
FastAPI HTTP endpoint'leri kaldırıldığı için bu script,
mesajları doğrudan analysis_queue'ya publish ederek
result_queue'dan sonuçları okur ve süreyi ölçer.

Kullanım:
    python benchmark.py
    python benchmark.py --n 5 --url https://example.com/photo.jpg
"""
from __future__ import annotations

import argparse
import json
import time
import uuid

import pika

RABBITMQ_HOST  = "localhost"
RABBITMQ_PORT  = 5672
RABBITMQ_USER  = "admin"
RABBITMQ_PASS  = "admin123"
ANALYSIS_QUEUE = "analysis_queue"
RESULT_QUEUE   = "result_queue"

DEFAULT_IMAGE_URL = (
    "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEgI8hbyGkUDAF7hItsu4gTbLgrcM7YJLvTEL494jT4TR_fK3YKb9FRiWd0ZZOWUFFB20ZsAkGAYDvcxR5d9WC7WTy29BnOCobwqhNlfSaDjam8POajCwHVRIJaC9pitYr9Zu1x4h30uWEbE/s1600/The_Last_Supper_Jacopo_Bassano_1542.jpg"
)


def get_channel():
    conn = pika.BlockingConnection(
        pika.ConnectionParameters(
            host        = RABBITMQ_HOST,
            port        = RABBITMQ_PORT,
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS),
        )
    )
    ch = conn.channel()
    ch.queue_declare(queue=ANALYSIS_QUEUE, durable=True)
    ch.queue_declare(queue=RESULT_QUEUE,   durable=True)
    return conn, ch


def send_and_wait(ch, image_url: str, timeout: int = 60) -> dict:
    """Tek mesaj gönder, result_queue'dan cevabı bekle."""
    record_id = str(uuid.uuid4())
    payload   = {"id": record_id, "image_url": image_url}

    start = time.time()
    ch.basic_publish(
        exchange    = "",
        routing_key = ANALYSIS_QUEUE,
        body        = json.dumps(payload),
        properties  = pika.BasicProperties(delivery_mode=2),
    )

    # Sonucu result_queue'dan polling ile oku
    deadline = time.time() + timeout
    while time.time() < deadline:
        method, props, body = ch.basic_get(queue=RESULT_QUEUE, auto_ack=True)
        if body:
            result  = json.loads(body)
            elapsed = round(time.time() - start, 2)
            if result.get("Id") == record_id:
                return {"elapsed": elapsed, "status": result.get("Status"), "result": result}
        time.sleep(0.2)

    return {"elapsed": round(time.time() - start, 2), "status": "TIMEOUT", "result": {}}


def run_benchmark(image_url: str, n: int):
    print(f"\n{'='*55}")
    print(f"  DeepFake Worker Benchmark  –  {n} mesaj")
    print(f"{'='*55}\n")

    try:
        conn, ch = get_channel()
        print("✅ RabbitMQ bağlantısı başarılı\n")
    except Exception as e:
        print(f"❌ RabbitMQ bağlantısı başarısız: {e}")
        print("   docker-compose up -d rabbitmq")
        return

    times = []
    for i in range(n):
        res  = send_and_wait(ch, image_url)
        icon = "✅" if res["status"] == "Completed" else f"❌ {res['status']}"
        print(f"  Mesaj {i+1}: {res['elapsed']:.2f}s  {icon}")
        times.append(res["elapsed"])

    conn.close()

    print(f"\n{'─'*55}")
    print(f"  Ortalama : {sum(times)/len(times):.2f}s")
    print(f"  En Hızlı : {min(times):.2f}s")
    print(f"  En Yavaş : {max(times):.2f}s")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DeepFake Worker Benchmark")
    parser.add_argument("--url", default=DEFAULT_IMAGE_URL, help="Test görüntü URL'si")
    parser.add_argument("--n",   type=int, default=3,       help="Tekrar sayısı")
    args = parser.parse_args()

    run_benchmark(args.url, args.n)
