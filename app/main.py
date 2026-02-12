"""
Deepfake Detection API  v3.1
============================
İş Akışı (5.7):
  1. Kullanıcı → .NET: görsel yükle
  2. .NET → DB: 'Processing' kaydı aç, görsel diske kaydet
  3. .NET → Python (bu API): id + image_url + original_image_path gönder
  4. Python: paralel analiz → base64 görseller + skorlar döndür
  5. .NET: base64'leri diske yaz, *Path sütunlarını güncelle
  6. .NET: thumbnail oluştur (150x150), ThumbnailPath yaz
  7. .NET → DB: Status='Completed'

Python tarafı:
  - Diske HİÇ BİR ŞEY yazmaz
  - Thumbnail OLUŞTURMAZ (.NET'in sorumluluğu)
  - ID ÜRETMEZHz (.NET'ten gelir, aynen döner)
  - Görseller base64 JPEG olarak döner
"""

import os
import time
import asyncio
import httpx
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .models import (
    AnalyzeUrlRequest,
    AnalysisResult,
    ElaResult,
    FftResult,
    MetadataResult,
    ModelResult,
    ErrorResponse,
)
from analysis import (
    analyze_ela,
    analyze_fft,
    analyze_metadata,
    simulate_model_prediction,
)

# ══════════════════════════════════════════════════════════════════
# KONFİGÜRASYON
# ══════════════════════════════════════════════════════════════════

API_KEY          = os.getenv("DEEPFAKE_API_KEY", "dev-secret-key-change-me")
API_KEY_DISABLED = os.getenv("DEEPFAKE_API_KEY_DISABLED", "false").lower() == "true"

_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/bmp"}
_MAX_BYTES    = 10 * 1024 * 1024  # 10 MB

_CPU  = multiprocessing.cpu_count()
_POOL = ThreadPoolExecutor(
    max_workers=min(_CPU * 2, 16),
    thread_name_prefix="analysis",
)

# ══════════════════════════════════════════════════════════════════
# API KEY MIDDLEWARE
# ══════════════════════════════════════════════════════════════════

_PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in _PUBLIC_PATHS or not path.startswith("/api/"):
            return await call_next(request)

        if API_KEY_DISABLED:
            print(f"⚠️  [API Key KAPALI] {request.method} {path}")
            return await call_next(request)

        provided_key = request.headers.get("X-API-Key", "")
        if not provided_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "X-API-Key header eksik"},
            )
        if provided_key != API_KEY:
            return JSONResponse(
                status_code=403,
                content={"detail": "Geçersiz API Key"},
            )

        return await call_next(request)


# ══════════════════════════════════════════════════════════════════
# UYGULAMA
# ══════════════════════════════════════════════════════════════════

_key_status = "🔓 KAPALI (geliştirme)" if API_KEY_DISABLED else "🔒 AKTİF"

app = FastAPI(
    title="Deepfake Detection API",
    version="3.1.0",
    description=f"""
## Deepfake Tespit API

**Görev dağılımı:**
- **Python (bu servis):** Analiz yapar, base64 görseller döner, diske yazmaz
- **.NET API:** Görseli diske kaydeder, thumbnail oluşturur, DB'yi günceller

**🔑 API Key:** {_key_status}

### Route'lar

| Endpoint           | Açıklama                          |
|--------------------|-----------------------------------|
| POST /api/analyze  | Tüm analizler (paralel)           |
| POST /api/ela      | Sadece ELA analizi                |
| POST /api/fft      | Sadece FFT analizi                |
| POST /api/metadata | Sadece Metadata / EXIF            |
| POST /api/model    | Sadece Model + Grad-CAM           |
| GET  /health       | Sağlık kontrolü                   |

### İstek Formatı
```json
{{
  "id": "550e8400-...",
  "image_url": "https://api.example.com/uploads/img.jpg",
  "original_image_path": "uploads/img.jpg"
}}
```
""",
)

app.add_middleware(ApiKeyMiddleware)


# ══════════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ══════════════════════════════════════════════════════════════════

async def _fetch_image(url: str) -> bytes:
    """URL'den görüntü indirir, doğrular, bytes döner."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
        except httpx.TimeoutException:
            raise HTTPException(status_code=408, detail="Görüntü URL'si zaman aşımına uğradı")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=400, detail=f"URL erişim hatası: {e.response.status_code}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"URL indirme hatası: {str(e)}")

    content_type = response.headers.get("content-type", "").split(";")[0].strip()
    if content_type not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail=f"Desteklenmeyen MIME: '{content_type}'. Kabul: {sorted(_ALLOWED_MIME)}",
        )

    image_bytes = response.content
    if len(image_bytes) > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Dosya çok büyük: {len(image_bytes)/1024/1024:.1f} MB (max 10 MB)",
        )

    return image_bytes


async def _run(fn, *args) -> Any:
    """Sync fonksiyonu thread pool'da asenkron çalıştırır."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_POOL, fn, *args)


# ══════════════════════════════════════════════════════════════════
# ROUTE 1 — Tam Analiz (paralel)
# ══════════════════════════════════════════════════════════════════

@app.post(
    "/api/analyze",
    response_model=AnalysisResult,
    summary="Tüm analizleri paralel çalıştırır",
    tags=["Analiz"],
)
async def analyze_all(body: AnalyzeUrlRequest):
    """
    Görüntüyü tüm yöntemlerle analiz eder (iş akışı adım 4).

    **Python tarafı:**
    - Model tahmini + Grad-CAM (base64)
    - ELA analizi + heatmap (base64)
    - FFT analizi + spektrum (base64)
    - Metadata / EXIF analizi

    **Python yapmaz (→ .NET'in sorumluluğu):**
    - Diske kaydetme
    - Thumbnail oluşturma (150x150, adım 6)
    - DB güncelleme (adım 7)
    """
    start = time.time()

    image_bytes = await _fetch_image(body.image_url)
    filename    = body.image_url.split("/")[-1].split("?")[0]

    # Paralel analiz (Thumbnail yok — .NET yapacak)
    results = await asyncio.gather(
        _run(simulate_model_prediction, image_bytes),
        _run(analyze_ela,               image_bytes),
        _run(analyze_fft,               image_bytes),
        _run(analyze_metadata,          image_bytes, filename),
        return_exceptions=True,
    )

    # Hata kontrolü
    names = ["Model", "ELA", "FFT", "Metadata"]
    for name, res in zip(names, results):
        if isinstance(res, Exception):
            return JSONResponse(
                status_code=500,
                content=ErrorResponse(
                    Id=body.id,
                    ErrorMessage=f"{name} analiz hatası: {res}",
                ).model_dump(mode="json"),
            )

    model_r, ela_r, fft_r, meta_r = results

    return AnalysisResult(
        Id = body.id,   # .NET'ten gelen, değişmez

        # CNN
        IsDeepfake    = model_r["is_deepfake"],
        CnnConfidence = model_r["confidence"],

        # Skorlar
        ElaScore        = ela_r["score"],
        FftAnomalyScore = fft_r["anomaly_score"],

        # Metadata
        ExifHasMetadata          = meta_r["has_metadata"],
        ExifCameraInfo           = meta_r["camera_info"],
        ExifSuspiciousIndicators = ";".join(meta_r["suspicious_indicators"]) or None,

        # Görseller (base64) — .NET diske yazar, *Path sütunlarını günceller
        GradcamImageBase64 = model_r["gradcam_b64"],
        ElaImageBase64     = ela_r["heatmap_b64"],
        FftImageBase64     = fft_r["spectrum_b64"],

        # İşlem süresi
        ProcessingTimeSeconds = round(time.time() - start, 2),
        Status = "Completed",
    )


# ══════════════════════════════════════════════════════════════════
# ROUTE 2 — Sadece ELA
# ══════════════════════════════════════════════════════════════════

@app.post(
    "/api/ela",
    response_model=ElaResult,
    summary="Sadece ELA analizi",
    tags=["Analiz"],
)
async def route_ela(body: AnalyzeUrlRequest):
    """Error Level Analysis — manipülasyon bölgelerini tespit eder."""
    image_bytes = await _fetch_image(body.image_url)
    result      = await _run(analyze_ela, image_bytes)
    return ElaResult(id=body.id, **result)


# ══════════════════════════════════════════════════════════════════
# ROUTE 3 — Sadece FFT
# ══════════════════════════════════════════════════════════════════

@app.post(
    "/api/fft",
    response_model=FftResult,
    summary="Sadece FFT analizi",
    tags=["Analiz"],
)
async def route_fft(body: AnalyzeUrlRequest):
    """Fast Fourier Transform — frekans alanı anomali tespiti."""
    image_bytes = await _fetch_image(body.image_url)
    result      = await _run(analyze_fft, image_bytes)
    return FftResult(id=body.id, **result)


# ══════════════════════════════════════════════════════════════════
# ROUTE 4 — Sadece Metadata
# ══════════════════════════════════════════════════════════════════

@app.post(
    "/api/metadata",
    response_model=MetadataResult,
    summary="Sadece Metadata / EXIF analizi",
    tags=["Analiz"],
)
async def route_metadata(body: AnalyzeUrlRequest):
    """EXIF ve dosya metadata analizi."""
    image_bytes = await _fetch_image(body.image_url)
    filename    = body.image_url.split("/")[-1].split("?")[0]
    result      = await _run(analyze_metadata, image_bytes, filename)
    return MetadataResult(
        id                    = body.id,
        has_metadata          = result["has_metadata"],
        camera_info           = result["camera_info"],
        suspicious_indicators = result["suspicious_indicators"],
    )


# ══════════════════════════════════════════════════════════════════
# ROUTE 5 — Sadece Model
# ══════════════════════════════════════════════════════════════════

@app.post(
    "/api/model",
    response_model=ModelResult,
    summary="Sadece Model tahmini + Grad-CAM",
    tags=["Analiz"],
)
async def route_model(body: AnalyzeUrlRequest):
    """ResNet50 sınıflandırma + Grad-CAM görselleştirme (simüle)."""
    image_bytes = await _fetch_image(body.image_url)
    result      = await _run(simulate_model_prediction, image_bytes)
    return ModelResult(id=body.id, **result)


# ══════════════════════════════════════════════════════════════════
# ROUTE 6 — Health / Root
# ══════════════════════════════════════════════════════════════════

@app.get("/health", tags=["Sistem"])
async def health():
    return {
        "status":          "healthy",
        "version":         "3.1.0",
        "cpu_count":       _CPU,
        "thread_workers":  _POOL._max_workers,
        "disk_writes":     False,
        "api_key_enabled": not API_KEY_DISABLED,
        "timestamp":       time.time(),
    }


@app.get("/", tags=["Sistem"])
async def root():
    return {
        "service":         "Deepfake Detection API",
        "version":         "3.1.0",
        "docs":            "/docs",
        "api_key_enabled": not API_KEY_DISABLED,
    }


# ── Shutdown ──────────────────────────────────────────────────────

@app.on_event("shutdown")
async def shutdown():
    _POOL.shutdown(wait=True)