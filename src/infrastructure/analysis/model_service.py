"""
Infrastructure: ModelService
==============================
IModelService'in somut implementasyonu.
ResNet50 simülasyonu + Grad-CAM görselleştirme.
"""
from __future__ import annotations

import io
import base64

import cv2
import numpy as np
from PIL import Image

from src.domain.entities.analysis_result import ModelMetrics
from src.domain.interfaces import IModelService


class ModelService(IModelService):
    """
    CNN Model Simülasyonu:
    Gerçek model eğitilene kadar heuristik tahmin ve
    gaussian blob tabanlı Grad-CAM kullanır.

    Değiştirmek için yalnızca bu sınıfı güncelleyin —
    domain ve application katmanları etkilenmez.
    """

    _INPUT_SIZE = 224  # ResNet50 standart girdi boyutu

    def analyze(self, image_bytes: bytes) -> ModelMetrics:
        img_bgr = self._to_bgr(image_bytes)
        gray    = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # Heuristik sınıflandırma
        noise      = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        smoothness = float(np.std(gray))

        if noise < 100 or smoothness < 30:
            is_deepfake = True
            confidence  = float(np.clip(0.75 + np.random.uniform(0, 0.20), 0, 1))
        else:
            is_deepfake = False
            confidence  = float(np.clip(0.65 + np.random.uniform(0, 0.30), 0, 1))

        # Grad-CAM simülasyonu (gaussian blob)
        h, w   = gray.shape
        cy, cx = h // 2, w // 2
        y, x   = np.ogrid[:h, :w]
        sigma  = h / 4.0

        heatmap = np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sigma ** 2))
        heatmap = (
            (heatmap - heatmap.min()) / (heatmap.max() - heatmap.min()) * 255
        ).astype(np.uint8)

        heatmap_colored = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
        superimposed    = cv2.addWeighted(img_bgr, 0.6, heatmap_colored, 0.4, 0)
        gradcam_b64     = self._to_b64(superimposed)

        return ModelMetrics(
            is_deepfake = is_deepfake,
            confidence  = round(confidence, 4),
            gradcam_b64 = gradcam_b64,
        )

    # ── Yardımcılar ───────────────────────────────────────────────

    def _to_bgr(self, image_bytes: bytes) -> np.ndarray:
        pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        pil = pil.resize((self._INPUT_SIZE, self._INPUT_SIZE), Image.Resampling.LANCZOS)
        return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

    @staticmethod
    def _to_b64(img: np.ndarray, quality: int = 90) -> str:
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise RuntimeError("Grad-CAM görseli encode edilemedi")
        return base64.b64encode(buf.tobytes()).decode("utf-8")
