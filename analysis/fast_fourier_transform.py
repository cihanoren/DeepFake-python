import io
import base64
import numpy as np
import cv2
from PIL import Image
from typing import Dict


def analyze_fft(image_bytes: bytes) -> Dict:
    """
    FFT Analizi - Frekans alanı anomali tespiti

    Dosya kaydetmez, sonuçları base64 olarak döner.

    Returns:
        dict: {
            anomaly_score : float  0-1
            spectrum_b64  : str    base64 JPEG
            metrics       : dict
        }
    """
    # Bytes → numpy grayscale
    img = _bytes_to_gray(image_bytes, max_size=512)

    # ── FFT ────────────────────────────────────────────────────────
    f_shift    = np.fft.fftshift(np.fft.fft2(img))
    magnitude  = np.abs(f_shift)
    mag_log    = np.log1p(magnitude)

    h, w       = magnitude.shape
    cy, cx     = h // 2, w // 2
    radius     = min(h, w) // 4
    y, x       = np.ogrid[:h, :w]

    # ── Metrikler ──────────────────────────────────────────────────
    # 1. Yüksek frekans oranı
    mask_low        = (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2
    high_freq_ratio = 1.0 - float(np.sum(magnitude[mask_low]) / (np.sum(magnitude) + 1e-10))

    # 2. Merkez yoğunluğu
    cr   = magnitude[max(0, cy - radius):cy + radius, max(0, cx - radius):cx + radius]
    center_intensity = float(np.mean(cr) / (np.mean(magnitude) + 1e-5))

    # 3. Spektral düzgünlük (örneklenmiş radyal profil)
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

    # ── Skor ───────────────────────────────────────────────────────
    score = 0
    if high_freq_ratio > 0.4:
        score += 30
    if center_intensity > 0.7:
        score += 45
    if spectral_smoothness < 0.25:
        score += 25

    # ── Görsel → base64 ───────────────────────────────────────────
    spectrum_vis    = cv2.normalize(mag_log, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    spectrum_colored = cv2.applyColorMap(spectrum_vis, cv2.COLORMAP_VIRIDIS)
    spectrum_b64    = _ndarray_to_b64(spectrum_colored)

    return {
        "anomaly_score": round(score / 100.0, 4),
        "spectrum_b64":  spectrum_b64,
        "metrics": {
            "high_freq_ratio":    round(high_freq_ratio, 3),
            "center_intensity":   round(center_intensity, 3),
            "spectral_smoothness": round(spectral_smoothness, 3),
        },
    }


# ── Yardımcı Fonksiyonlar ──────────────────────────────────────────

def _bytes_to_gray(image_bytes: bytes, max_size: int = 512) -> np.ndarray:
    pil_img = Image.open(io.BytesIO(image_bytes)).convert("L")
    if max(pil_img.size) > max_size:
        pil_img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    return np.array(pil_img)


def _ndarray_to_b64(img: np.ndarray, quality: int = 90) -> str:
    success, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        raise RuntimeError("Görsel encode edilemedi")
    return base64.b64encode(buf.tobytes()).decode("utf-8")