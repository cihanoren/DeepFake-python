"""
Domain Entity: AnalysisRequest
================================
Worker'ın analysis_queue'dan tükettiği ham mesajı temsil eder.
Hiçbir dış katmana bağımlı değildir.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisRequest:
    """
    Değiştirilemez (immutable) istek nesnesi.

    Alanlar:
        record_id  – .NET tarafından üretilen UUID (string)
        image_url  – İndirilecek görselin tam URL'si
    """
    record_id: str
    image_url: str

    # ── Fabrika ──────────────────────────────────────────────────────
    @classmethod
    def from_dict(cls, data: dict) -> AnalysisRequest:
        """
        RabbitMQ mesaj gövdesinden (dict) entity oluşturur.

        Raises:
            ValueError: Zorunlu alan eksikse
        """
        record_id = data.get("id") or data.get("record_id")
        image_url = data.get("image_url")

        if not record_id:
            raise ValueError("Mesajda 'id' alanı zorunludur")
        if not image_url:
            raise ValueError("Mesajda 'image_url' alanı zorunludur")

        return cls(record_id=str(record_id), image_url=str(image_url))
