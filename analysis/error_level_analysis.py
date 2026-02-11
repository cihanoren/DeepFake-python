import io
import base64
import tempfile
import os
import numpy as np
import cv2
from PIL import Image, ImageChops
from typing import Dict


def analyze_ela(image_bytes: bytes) -> Dict:
    """
    ELA Analizi - JPEG manipülasyon tespiti

    Dosya kaydetmez, sonuçları base64 olarak döner.

    Returns:
        dict: {
            score        : float  0-1
            heatmap_b64  : str    base64 JPEG
            metrics      : dict
        }
    """
    # Bytes → PIL
    original = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # Boyutu kısıtla (hız)
    max_size = 800
    if max(original.size) > max_size:
        original.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

    # Tek kalite seviyesi ile ELA
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        original.save(tmp_path, "JPEG", quality=85)
        compressed = Image.open(tmp_path).convert("RGB")
        diff = ImageChops.difference(original, compressed)
        diff_np = np.array(diff)
    finally:
        os.remove(tmp_path)

    # Normalize
    final_ela = cv2.normalize(diff_np, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    gray_ela  = cv2.cvtColor(final_ela, cv2.COLOR_RGB2GRAY)

    # ── Metrikler ──────────────────────────────────────────────────
    homogeneity      = 1.0 - (np.std(gray_ela) / (np.mean(gray_ela) + 1e-5))
    regional_variance = _grid_variance(gray_ela, grid_size=64)
    edges            = cv2.Canny(gray_ela, 50, 150)
    edge_density     = float(np.sum(edges > 0) / edges.size)

    # ── Skor ───────────────────────────────────────────────────────
    score = 0
    if homogeneity < 0.3:
        score += 35
    if regional_variance > 50:
        score += 40
    if edge_density > 0.15:
        score += 25

    # ── Görsel → base64 ───────────────────────────────────────────
    heatmap     = cv2.applyColorMap(gray_ela, cv2.COLORMAP_JET)
    heatmap_b64 = _ndarray_to_b64(heatmap)

    return {
        "score":       round(score / 100.0, 4),
        "heatmap_b64": heatmap_b64,
        "metrics": {
            "homogeneity":       round(float(homogeneity), 3),
            "regional_variance": round(float(regional_variance), 2),
            "edge_density":      round(edge_density, 3),
        },
    }


# ── Yardımcı Fonksiyonlar ──────────────────────────────────────────

def _grid_variance(gray: np.ndarray, grid_size: int) -> float:
    h, w = gray.shape
    variances = [
        float(np.var(gray[i:i + grid_size, j:j + grid_size]))
        for i in range(0, h, grid_size)
        for j in range(0, w, grid_size)
        if gray[i:i + grid_size, j:j + grid_size].size > 0
    ]
    return float(np.std(variances)) if variances else 0.0


def _ndarray_to_b64(img: np.ndarray, quality: int = 90) -> str:
    """OpenCV ndarray → base64 JPEG string"""
    success, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        raise RuntimeError("Görsel encode edilemedi")
    return base64.b64encode(buf.tobytes()).decode("utf-8")