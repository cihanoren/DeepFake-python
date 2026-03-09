"""
Domain Interfaces (Sözleşmeler)
================================
Tüm dış bağımlılıklar bu soyut sözleşmeler üzerinden kullanılır.
Bağımlılık kuralı: yalnızca içe doğru (domain hiçbir şeye bağlı değil).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from src.domain.entities.analysis_request import AnalysisRequest
from src.domain.entities.analysis_result import (
    AnalysisResult,
    ElaMetrics,
    FftMetrics,
    MetadataMetrics,
    ModelMetrics,
)


# ══════════════════════════════════════════════════════════════════
# GÖRSEL İNDİRME
# ══════════════════════════════════════════════════════════════════

class IImageDownloader(ABC):
    """Verilen URL'den görsel baytlarını indirir."""

    @abstractmethod
    def download(self, url: str) -> bytes:
        ...


# ══════════════════════════════════════════════════════════════════
# TEKİL ANALİZ SERVİSLERİ
# ══════════════════════════════════════════════════════════════════

class IElaService(ABC):
    @abstractmethod
    def analyze(self, image_bytes: bytes) -> ElaMetrics:
        ...


class IFftService(ABC):
    @abstractmethod
    def analyze(self, image_bytes: bytes) -> FftMetrics:
        ...


class IMetadataService(ABC):
    @abstractmethod
    def analyze(self, image_bytes: bytes, filename: str) -> MetadataMetrics:
        ...


class IModelService(ABC):
    @abstractmethod
    def analyze(self, image_bytes: bytes) -> ModelMetrics:
        ...


# ══════════════════════════════════════════════════════════════════
# PARALELLEŞTİRİCİ
# ══════════════════════════════════════════════════════════════════

class IAnalysisOrchestrator(ABC):
    """
    4 analiz servisini eş zamanlı çalıştırır ve
    birleşik AnalysisResult döner.
    """

    @abstractmethod
    def run(self, request: AnalysisRequest, image_bytes: bytes) -> AnalysisResult:
        ...


# ══════════════════════════════════════════════════════════════════
# MESAJLAŞMA
# ══════════════════════════════════════════════════════════════════

MessageHandler = Callable[[dict], None]


class IMessageConsumer(ABC):
    """Bir kuyruktan mesaj tüketir."""

    @abstractmethod
    def start_consuming(self, queue_name: str, on_message: MessageHandler) -> None:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...


class IMessagePublisher(ABC):
    """Bir kuyruğa mesaj yayınlar."""

    @abstractmethod
    def publish(self, queue_name: str, payload: dict) -> None:
        ...
