"""
Infrastructure: ParallelAnalysisOrchestrator
=============================================
IAnalysisOrchestrator'ın somut implementasyonu.
ThreadPoolExecutor ile 4 analizi aynı anda çalıştırır.
Toplam süre ≈ en yavaş analizin süresi.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from src.domain.entities.analysis_request import AnalysisRequest
from src.domain.entities.analysis_result import AnalysisResult
from src.domain.interfaces import (
    IAnalysisOrchestrator,
    IElaService,
    IFftService,
    IMetadataService,
    IModelService,
)

log = logging.getLogger("orchestrator.parallel")


class ParallelAnalysisOrchestrator(IAnalysisOrchestrator):
    """
    4 bağımsız analiz servisini ThreadPool üzerinde paralel çalıştırır.
    Herhangi bir servis hata verirse RuntimeError fırlatır.
    """

    def __init__(
        self,
        ela_service:      IElaService,
        fft_service:      IFftService,
        metadata_service: IMetadataService,
        model_service:    IModelService,
        thread_pool:      ThreadPoolExecutor,
    ) -> None:
        self._ela      = ela_service
        self._fft      = fft_service
        self._metadata = metadata_service
        self._model    = model_service
        self._pool     = thread_pool

    def run(self, request: AnalysisRequest, image_bytes: bytes) -> AnalysisResult:
        filename = request.image_url.split("/")[-1].split("?")[0] or "image.jpg"

        log.info("  ⚡ Paralel analiz başlatıldı (4 thread)...")
        start = time.perf_counter()

        futures: dict[Any, str] = {
            self._pool.submit(self._model.analyze,    image_bytes):          "model",
            self._pool.submit(self._ela.analyze,      image_bytes):          "ela",
            self._pool.submit(self._fft.analyze,      image_bytes):          "fft",
            self._pool.submit(self._metadata.analyze, image_bytes, filename): "meta",
        }

        results: dict[str, Any] = {}

        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
                log.info("  ✓ %s tamamlandı", name.upper())
            except Exception as exc:
                log.error("  ✗ %s hatası: %s", name.upper(), exc, exc_info=True)
                raise RuntimeError(f"{name} analizi başarısız: {exc}") from exc

        elapsed = round(time.perf_counter() - start, 2)

        return AnalysisResult(
            record_id               = request.record_id,
            model                   = results["model"],
            ela                     = results["ela"],
            fft                     = results["fft"],
            meta                    = results["meta"],
            processing_time_seconds = elapsed,
        )
