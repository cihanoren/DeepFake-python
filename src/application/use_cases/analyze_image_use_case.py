"""
Application Use Case: AnalyzeImageUseCase
==========================================
İş kurallarını yönetir. Hangi altyapının kullanıldığını bilmez;
yalnızca domain arayüzlerine bağımlıdır.

Akış:
  1. dict mesajını → AnalysisRequest entity'sine dönüştür
  2. Görseli indir
  3. Paralel analiz orchestrator'ını çağır
  4. Sonucu result_queue'ya yayınla
  5. Hata olursa FailedAnalysisResult yayınla
"""
from __future__ import annotations

import logging

from src.domain.entities.analysis_request import AnalysisRequest
from src.domain.entities.analysis_result import FailedAnalysisResult
from src.domain.interfaces import (
    IAnalysisOrchestrator,
    IImageDownloader,
    IMessagePublisher,
)

log = logging.getLogger("use_case.analyze_image")


class AnalyzeImageUseCase:
    """
    Tek sorumluluk: bir analiz mesajını uçtan uca işle.

    Bağımlılıklar constructor injection ile enjekte edilir
    (Dependency Inversion Principle).
    """

    def __init__(
        self,
        downloader:   IImageDownloader,
        orchestrator: IAnalysisOrchestrator,
        publisher:    IMessagePublisher,
        result_queue: str,
    ) -> None:
        self._downloader   = downloader
        self._orchestrator = orchestrator
        self._publisher    = publisher
        self._result_queue = result_queue

    # ──────────────────────────────────────────────────────────────
    def execute(self, raw_message: dict) -> None:
        """
        Kuyruktan gelen ham dict'i işler.
        Her zaman result_queue'ya bir mesaj üretir (başarı veya hata).
        """
        record_id = raw_message.get("id", "unknown")

        try:
            # 1. Parse
            request = AnalysisRequest.from_dict(raw_message)
            log.info("▶ Yeni görev | ID: %s", request.record_id)

            # 2. İndir
            log.info("  ↓ İndiriliyor: %.90s", request.image_url)
            image_bytes = self._downloader.download(request.image_url)

            # 3. Paralel analiz
            result = self._orchestrator.run(request, image_bytes)

            # 4. Yayınla
            self._publisher.publish(self._result_queue, result.to_dict())
            log.info(
                "✔ Tamamlandı | ID: %s | Süre: %.2fs",
                result.record_id,
                result.processing_time_seconds,
            )

        except Exception as exc:
            log.error("✘ Hata | ID: %s | %s", record_id, exc, exc_info=True)
            self._publish_failure(record_id, exc)

    # ── Yardımcı ──────────────────────────────────────────────────
    def _publish_failure(self, record_id: str, exc: Exception) -> None:
        payload = FailedAnalysisResult(
            record_id=record_id,
            error_message=str(exc),
        ).to_dict()
        try:
            self._publisher.publish(self._result_queue, payload)
        except Exception as pub_exc:
            log.error("  Hata payload gönderilemedi: %s", pub_exc)
