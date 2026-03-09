"""
Infrastructure: ElaService
===========================
IElaService'in somut implementasyonu.
Piksel tabanlı JPEG sıkıştırma fark analizi yapar.
"""
from __future__ import annotations

import io
import base64
import tempfile
import os

import cv2
import numpy as np
from PIL import Image, ImageChops

from src.domain.entities.analysis_result import ElaMetrics
from src.domain.interfaces import IElaService


class ElaService(IElaService):
    """
    Error Level Analysis:
    Görseli belirli bir kalitede yeniden sıkıştırır ve orijinal ile
    farkını hesaplayarak manipülasyon bölgelerini tespit eder.
    """

    _QUALITY  = 85
    _MAX_SIZE = 800

    def analyze(self, image_bytes: bytes) -> ElaMetrics:
        original = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Boyut kısıtı (hız)
        if max(original.size) > self._MAX_SIZE:
            original.thumbnail((self._MAX_SIZE, self._MAX_SIZE), Image.Resampling.LANCZOS)

        # Geçici dosya üzerinden yeniden sıkıştırma
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            original.save(tmp_path, "JPEG", quality=self._QUALITY)
            compressed = Image.open(tmp_path).convert("RGB")
            diff       = ImageChops.difference(original, compressed)
            diff_np    = np.array(diff)
        finally:
            os.remove(tmp_path)

        # Normalize
        ela_norm = cv2.normalize(diff_np, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        gray_ela = cv2.cvtColor(ela_norm, cv2.COLOR_RGB2GRAY)

        # Metrikler
        homogeneity      = 1.0 - (np.std(gray_ela) / (np.mean(gray_ela) + 1e-5))
        regional_variance = self._grid_variance(gray_ela, grid_size=64)
        edges            = cv2.Canny(gray_ela, 50, 150)
        edge_density     = float(np.sum(edges > 0) / edges.size)

        # Kural tabanlı skor (0-100 → 0-1)
        score = 0
        if homogeneity < 0.3:
            score += 35
        if regional_variance > 50:
            score += 40
        if edge_density > 0.15:
            score += 25

        heatmap     = cv2.applyColorMap(gray_ela, cv2.COLORMAP_JET)
        heatmap_b64 = self._to_b64(heatmap)

        return ElaMetrics(
            score             = round(score / 100.0, 4),
            heatmap_b64       = heatmap_b64,
            homogeneity       = round(float(homogeneity), 3),
            regional_variance = round(float(regional_variance), 2),
            edge_density      = round(edge_density, 3),
        )

    # ── Yardımcılar ───────────────────────────────────────────────

    @staticmethod
    def _grid_variance(gray: np.ndarray, grid_size: int) -> float:
        h, w = gray.shape
        variances = [
            float(np.var(gray[i:i + grid_size, j:j + grid_size]))
            for i in range(0, h, grid_size)
            for j in range(0, w, grid_size)
            if gray[i:i + grid_size, j:j + grid_size].size > 0
        ]
        return float(np.std(variances)) if variances else 0.0

    @staticmethod
    def _to_b64(img: np.ndarray, quality: int = 90) -> str:
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise RuntimeError("ELA görseli encode edilemedi")
        return base64.b64encode(buf.tobytes()).decode("utf-8")
