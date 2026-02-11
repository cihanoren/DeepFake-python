import io
import os
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime
from typing import Dict, List, Optional


def analyze_metadata(image_bytes: bytes, filename: str = "") -> Dict:
    """
    Metadata / EXIF Analizi

    Returns:
        dict: {
            has_metadata          : bool
            camera_info           : str | None
            suspicious_indicators : list[str]
            exif_summary          : dict
        }
    """
    img = Image.open(io.BytesIO(image_bytes))

    exif_data     = img.getexif()
    has_metadata  = bool(exif_data)
    camera_info: Optional[str] = None
    suspicious:  List[str]     = []
    exif_summary: Dict         = {}

    if not has_metadata:
        suspicious.append("EXIF verisi yok")
    else:
        exif_summary = {TAGS.get(k, str(k)): _safe_val(v) for k, v in exif_data.items()}

        # Kamera bilgisi
        make  = exif_summary.get("Make", "")
        model = exif_summary.get("Model", "")
        if make or model:
            camera_info = f"{make} {model}".strip()
        else:
            suspicious.append("Kamera bilgisi eksik")

        # Software – AI araç kontrolü
        _AI_KEYWORDS = [
            "midjourney", "dall-e", "dall·e", "stable diffusion",
            "comfyui", "automatic1111", "openai", "generator",
            "synthetic", "ai generated",
        ]
        software = str(exif_summary.get("Software", "")).lower()
        if software and any(kw in software for kw in _AI_KEYWORDS):
            suspicious.append(f"AI yazılımı tespit edildi: {exif_summary.get('Software')}")

        # Tarih anomalisi
        date_str = exif_summary.get("DateTime", "")
        if date_str:
            try:
                dt = datetime.strptime(str(date_str), "%Y:%m:%d %H:%M:%S")
                if dt.year < 2000 or dt > datetime.utcnow():
                    suspicious.append("Tarih anomalisi")
            except ValueError:
                suspicious.append("Tarih formatı geçersiz")

    # Dosya boyutu (bytes)
    size_kb = len(image_bytes) / 1024.0
    if size_kb < 100:
        suspicious.append(f"Küçük dosya boyutu ({size_kb:.1f} KB)")

    # PNG + EXIF birlikteliği
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".png" and has_metadata:
        suspicious.append("PNG formatında EXIF (olağandışı)")

    return {
        "has_metadata":          has_metadata,
        "camera_info":           camera_info,
        "suspicious_indicators": suspicious,
        "exif_summary":          exif_summary,
    }


def _safe_val(v) -> str:
    """EXIF değerini JSON-safe string'e çevir"""
    try:
        if isinstance(v, bytes):
            return v.decode("utf-8", errors="replace")
        return str(v)
    except Exception:
        return ""