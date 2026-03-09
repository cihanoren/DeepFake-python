"""
Infrastructure: HttpImageDownloader
=====================================
IImageDownloader'ın somut implementasyonu.
requests kütüphanesi ile URL'den görsel indirir.
"""
from __future__ import annotations

import requests

from src.domain.interfaces import IImageDownloader


class HttpImageDownloader(IImageDownloader):
    """
    Standart HTTP GET ile görsel indirir.
    Timeout, boyut limiti ve MIME kontrolü içerir.
    """

    _ALLOWED_MIME = frozenset({
        "image/jpeg", "image/png", "image/webp", "image/bmp",
    })
    _MAX_BYTES    = 10 * 1024 * 1024  # 10 MB
    _TIMEOUT      = 15                 # saniye

    def download(self, url: str) -> bytes:
        """
        Raises:
            ValueError: MIME tipi desteklenmiyorsa
            ValueError: Dosya çok büyükse
            requests.HTTPError: HTTP hata kodu dönerse
            requests.Timeout: Zaman aşımı
        """
        response = requests.get(url, timeout=self._TIMEOUT, stream=True)
        response.raise_for_status()

        # MIME kontrolü
        content_type = response.headers.get("content-type", "").split(";")[0].strip()
        if content_type not in self._ALLOWED_MIME:
            raise ValueError(
                f"Desteklenmeyen MIME tipi: '{content_type}'. "
                f"Kabul edilenler: {sorted(self._ALLOWED_MIME)}"
            )

        # Boyut kontrolü (streaming)
        chunks: list[bytes] = []
        downloaded = 0
        for chunk in response.iter_content(chunk_size=65_536):
            downloaded += len(chunk)
            if downloaded > self._MAX_BYTES:
                raise ValueError(
                    f"Dosya boyutu limiti aşıldı "
                    f"(max {self._MAX_BYTES // 1024 // 1024} MB)"
                )
            chunks.append(chunk)

        return b"".join(chunks)
