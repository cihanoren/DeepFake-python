import os
from pathlib import Path

# Dizin yapısı
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"

# Alt dizinler
GRADCAM_DIR = OUTPUT_DIR / "gradcam"
ELA_DIR = OUTPUT_DIR / "ela"
FFT_DIR = OUTPUT_DIR / "fft"
THUMBNAIL_DIR = OUTPUT_DIR / "thumbnails"

# Dizinleri oluştur
for directory in [UPLOAD_DIR, GRADCAM_DIR, ELA_DIR, FFT_DIR, THUMBNAIL_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# API ayarları
API_TITLE = "Deepfake Detection API"
API_VERSION = "1.0.0"
API_DESCRIPTION = """
ResNet50 tabanlı deepfake tespit API'si.

## Özellikler
- CNN Sınıflandırma (ResNet50 - Simüle)
- Grad-CAM Görselleştirme
- Error Level Analysis (ELA)
- Fast Fourier Transform (FFT)
- EXIF Metadata Analizi
"""

# Timeout ayarları
REQUEST_TIMEOUT = 60  # saniye

# İzin verilen dosya türleri
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB