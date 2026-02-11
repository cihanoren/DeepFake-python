import io
import base64
import numpy as np
import cv2
from PIL import Image
from typing import Dict


def simulate_model_prediction(image_bytes: bytes) -> Dict:
    """
    ResNet50 model tahmini simülasyonu (model eğitilene kadar)

    Dosya kaydetmez, Grad-CAM görselini base64 olarak döner.

    Returns:
        dict: {
            is_deepfake  : bool
            confidence   : float  0-1
            gradcam_b64  : str    base64 JPEG
        }
    """
    # Bytes → BGR (224x224 – ResNet50 boyutu)
    img_bgr  = _bytes_to_bgr(image_bytes, size=224)
    gray     = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # ── Basit heuristik tahmin ─────────────────────────────────────
    noise      = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    smoothness = float(np.std(gray))

    if noise < 100 or smoothness < 30:
        is_deepfake = True
        confidence  = float(np.clip(0.75 + np.random.uniform(0, 0.20), 0, 1))
    else:
        is_deepfake = False
        confidence  = float(np.clip(0.65 + np.random.uniform(0, 0.30), 0, 1))

    # ── Grad-CAM simülasyonu (gaussian blob) ──────────────────────
    h, w     = gray.shape
    cy, cx   = h // 2, w // 2
    y, x     = np.ogrid[:h, :w]
    sigma    = h / 4.0
    heatmap  = np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sigma ** 2))
    heatmap  = ((heatmap - heatmap.min()) / (heatmap.max() - heatmap.min()) * 255).astype(np.uint8)

    heatmap_colored = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
    superimposed    = cv2.addWeighted(img_bgr, 0.6, heatmap_colored, 0.4, 0)

    gradcam_b64 = _ndarray_to_b64(superimposed)

    return {
        "is_deepfake": is_deepfake,
        "confidence":  round(confidence, 4),
        "gradcam_b64": gradcam_b64,
    }


# ── Yardımcı Fonksiyonlar ──────────────────────────────────────────

def _bytes_to_bgr(image_bytes: bytes, size: int = 224) -> np.ndarray:
    pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    pil_img = pil_img.resize((size, size), Image.Resampling.LANCZOS)
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def _ndarray_to_b64(img: np.ndarray, quality: int = 90) -> str:
    success, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        raise RuntimeError("Görsel encode edilemedi")
    return base64.b64encode(buf.tobytes()).decode("utf-8")