"""
Worker: Config
==============
Tüm ortam değişkenlerini tek noktada toplar.
Diğer modüller doğrudan os.getenv çağırmaz; bu sınıfı kullanır.
"""
from __future__ import annotations

import multiprocessing
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    # RabbitMQ
    rabbitmq_host: str
    rabbitmq_port: int
    rabbitmq_user: str
    rabbitmq_pass: str
    rabbitmq_url:  str | None   # Railway / CloudAMQP tam URL (öncelikli)

    # Kuyruklar
    analysis_queue: str
    result_queue:   str

    # ThreadPool
    worker_threads: int

    @classmethod
    def from_env(cls) -> "Config":
        cpu            = multiprocessing.cpu_count()
        worker_threads = int(os.getenv("WORKER_THREADS", str(min(cpu * 2, 16))))

        return cls(
            rabbitmq_host  = os.getenv("RABBITMQ_HOST",  "localhost"),
            rabbitmq_port  = int(os.getenv("RABBITMQ_PORT", "5672")),
            rabbitmq_user  = os.getenv("RABBITMQ_USER",  "admin"),
            rabbitmq_pass  = os.getenv("RABBITMQ_PASS",  "admin123"),
            rabbitmq_url   = os.getenv("RABBITMQ_URL"),   # Yoksa None
            analysis_queue = os.getenv("ANALYSIS_QUEUE", "analysis_queue"),
            result_queue   = os.getenv("RESULT_QUEUE",   "result_queue"),
            worker_threads = worker_threads,
        )
