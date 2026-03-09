"""
Infrastructure: MetadataService
================================
IMetadataService'in somut implementasyonu.
EXIF verisi üzerinden metadata anomalisi tespit eder.
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from typing import Optional

from PIL import Image
from PIL.ExifTags import TAGS

from src.domain.entities.analysis_result import MetadataMetrics
from src.domain.interfaces import IMetadataService


class MetadataService(IMetadataService):
    """
    Metadata / EXIF Analizi:
    - Kamera bilgisi eksikliği
    - AI üretim yazılımı tespiti
    - Tarih anomalisi
    - Dosya boyutu şüphesi
    - PNG + EXIF çelişkisi
    """

    _AI_KEYWORDS = frozenset({
        "midjourney", "dall-e", "dall·e", "stable diffusion",
        "comfyui", "automatic1111", "openai", "generator",
        "synthetic", "ai generated",
    })

    def analyze(self, image_bytes: bytes, filename: str = "") -> MetadataMetrics:
        img      = Image.open(io.BytesIO(image_bytes))
        exif_raw = img.getexif()

        has_metadata = bool(exif_raw)
        camera_info: Optional[str] = None
        suspicious: list[str]      = []

        if not has_metadata:
            suspicious.append("EXIF verisi yok")
        else:
            exif = {TAGS.get(k, str(k)): self._safe(v) for k, v in exif_raw.items()}

            # Kamera
            make  = exif.get("Make", "")
            model = exif.get("Model", "")
            if make or model:
                camera_info = f"{make} {model}".strip()
            else:
                suspicious.append("Kamera bilgisi eksik")

            # AI yazılım tespiti
            software = str(exif.get("Software", "")).lower()
            if software and any(kw in software for kw in self._AI_KEYWORDS):
                suspicious.append(f"AI yazılımı tespit edildi: {exif.get('Software')}")

            # Tarih anomalisi
            date_str = exif.get("DateTime", "")
            if date_str:
                try:
                    dt = datetime.strptime(str(date_str), "%Y:%m:%d %H:%M:%S")
                    if dt.year < 2000 or dt > datetime.utcnow():
                        suspicious.append("Tarih anomalisi")
                except ValueError:
                    suspicious.append("Tarih formatı geçersiz")

        # Küçük dosya kontrolü
        size_kb = len(image_bytes) / 1024.0
        if size_kb < 100:
            suspicious.append(f"Küçük dosya boyutu ({size_kb:.1f} KB)")

        # PNG + EXIF çelişkisi
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".png" and has_metadata:
            suspicious.append("PNG formatında EXIF (olağandışı)")

        return MetadataMetrics(
            has_metadata          = has_metadata,
            camera_info           = camera_info,
            suspicious_indicators = suspicious,
        )

    # ── Yardımcı ──────────────────────────────────────────────────

    @staticmethod
    def _safe(value) -> str:
        try:
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            return str(value)
        except Exception:
            return ""
