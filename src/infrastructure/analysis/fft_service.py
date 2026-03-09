"""
Infrastructure: FftService
===========================
IFftService'in somut implementasyonu.
Frekans alanı anomali tespiti yapar.
"""
from __future__ import annotations

import io
import base64

import cv2
import numpy as np
from PIL import Image

from src.domain.entities.analysis_result import FftMetrics
from src.domain.interfaces import IFftService


class FftService(IFftService):
    """
    Fast Fourier Transform Analizi:
    Görselin frekans spektrumunu analiz ederek üretken model
    parmak izlerini ve sıkıştırma anomalilerini tespit eder.
    """

    _MAX_SIZE = 512

    def analyze(self, image_bytes: bytes) -> FftMetrics:
        img = self._to_gray(image_bytes)

        f_shift   = np.fft.fftshift(np.fft.fft2(img))
        magnitude = np.abs(f_shift)
        mag_log   = np.log1p(magnitude)

        h, w   = magnitude.shape
        cy, cx = h // 2, w // 2
        radius = min(h, w) // 4
        y, x   = np.ogrid[:h, :w]

        # Yüksek frekans oranı
        mask_low        = (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2
        high_freq_ratio = 1.0 - float(
            np.sum(magnitude[mask_low]) / (np.sum(magnitude) + 1e-10)
        )

        # Merkez yoğunluğu
        cr = magnitude[
            max(0, cy - radius): cy + radius,
            max(0, cx - radius): cx + radius,
        ]
        center_intensity = float(np.mean(cr) / (np.mean(magnitude) + 1e-5))

        # Radyal spektral düzgünlük
        dists          = np.sqrt((x - cx) ** 2 + (y - cy) ** 2).astype(int)
        radial_profile = [
            float(np.mean(magnitude[(dists >= r) & (dists < r + 10)]))
            for r in range(1, min(h, w) // 2, 10)
            if np.sum((dists >= r) & (dists < r + 10)) > 0
        ]
        spectral_smoothness = float(
            np.std(radial_profile) / (np.mean(radial_profile) + 1e-5)
            if radial_profile else 0.0
        )

        # Kural tabanlı skor
        score = 0
        if high_freq_ratio > 0.4:
            score += 30
        if center_intensity > 0.7:
            score += 45
        if spectral_smoothness < 0.25:
            score += 25

        spectrum_vis     = cv2.normalize(mag_log, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        spectrum_colored = cv2.applyColorMap(spectrum_vis, cv2.COLORMAP_VIRIDIS)
        spectrum_b64     = self._to_b64(spectrum_colored)

        return FftMetrics(
            anomaly_score       = round(score / 100.0, 4),
            spectrum_b64        = spectrum_b64,
            high_freq_ratio     = round(high_freq_ratio, 3),
            center_intensity    = round(center_intensity, 3),
            spectral_smoothness = round(spectral_smoothness, 3),
        )

    # ── Yardımcılar ───────────────────────────────────────────────

    def _to_gray(self, image_bytes: bytes) -> np.ndarray:
        pil = Image.open(io.BytesIO(image_bytes)).convert("L")
        if max(pil.size) > self._MAX_SIZE:
            pil.thumbnail((self._MAX_SIZE, self._MAX_SIZE), Image.Resampling.LANCZOS)
        return np.array(pil)

    @staticmethod
    def _to_b64(img: np.ndarray, quality: int = 90) -> str:
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise RuntimeError("FFT görseli encode edilemedi")
        return base64.b64encode(buf.tobytes()).decode("utf-8")
