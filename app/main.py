"""
Deepfake Detection API  v3.0
============================
- Her analiz kendi route'unda çalışır
- ID .NET tarafından gelir, Python üretmez
- Static API Key koruması (Swagger için bypass modu)
- Görseller base64 döner, diske yazılmaz
"""

import io
import os
import base64
import time
import asyncio
import httpx
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import FastAPI, HTTPException, Security, Request
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from PIL import Image

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

# API Key ayarları
# Değer env variable'dan okunur; yoksa varsayılan dev key kullanılır.
API_KEY         = os.getenv("DEEPFAKE_API_KEY", "dev-secret-key-change-me")

# True → Key kontrolü KAPALI (sadece geliştirme ortamı için)
# Swagger'da patlamayı önler; prod'da False yapın veya env'den okuyun.
API_KEY_DISABLED = os.getenv("DEEPFAKE_API_KEY_DISABLED", "false").lower() == "true"

_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/bmp"}
_MAX_BYTES    = 10 * 1024 * 1024  # 10 MB

# Thread pool
_CPU  = multiprocessing.cpu_count()
_POOL = ThreadPoolExecutor(
    max_workers=min(_CPU * 2, 16),
    thread_name_prefix="analysis",
)

# ══════════════════════════════════════════════════════════════════
# API KEY MIDDLEWARE
# ══════════════════════════════════════════════════════════════════

_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Bu path'ler key kontrolünden muaf (Swagger, health vb.)
_PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """
    Tüm /api/* route'larını X-API-Key header ile korur.
    API_KEY_DISABLED=true ise sadece uyarı log'lar, engel çıkarmaz.
    """
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Public path → doğrulama yok
        if path in _PUBLIC_PATHS or not path.startswith("/api/"):
            return await call_next(request)

        # Key kontrolü devre dışıysa sadece uyar
        if API_KEY_DISABLED:
            print(f"⚠️  [API Key KAPALI] {request.method} {path}")
            return await call_next(request)

        # Key kontrolü
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

_key_status = "🔓 KAPALI (geliştirme modu)" if API_KEY_DISABLED else "🔒 AKTİF"

app = FastAPI(
    title="Deepfake Detection API",
    version="3.0.0",
    description=f"""
## Deepfake Tespit API

Tüm analizler **URL** üzerinden çalışır, diske **hiçbir şey yazmaz**.  
Görseller **base64 JPEG** olarak yanıtta döner.  
ID değeri her zaman **.NET tarafından** gönderilir.

### 🔑 API Key Durumu: {_key_status}

API Key kontrolünü açmak/kapatmak için:
```
DEEPFAKE_API_KEY_DISABLED=true   # Swagger testi için kapat
DEEPFAKE_API_KEY_DISABLED=false  # Production için aç (varsayılan)
DEEPFAKE_API_KEY=your-secret     # Key değerini değiştir
```

### Route'lar

| Endpoint           | Açıklama                          |
|--------------------|-----------------------------------|
| POST /api/analyze  | Tüm analizleri paralel çalıştırır |
| POST /api/ela      | Sadece ELA analizi                |
| POST /api/fft      | Sadece FFT analizi                |
| POST /api/metadata | Sadece Metadata analizi           |
| POST /api/model    | Sadece Model tahmini + Grad-CAM   |
| GET  /health       | Sağlık kontrolü                   |
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
            detail=f"Desteklenmeyen MIME türü: '{content_type}'. Kabul edilen: {sorted(_ALLOWED_MIME)}",
        )

    image_bytes = response.content
    if len(image_bytes) > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Dosya çok büyük: {len(image_bytes)/1024/1024:.1f} MB (max 10 MB)",
        )

    return image_bytes


def _make_thumbnail_b64(image_bytes: bytes, size: tuple = (256, 256)) -> str:
    """Thumbnail oluşturup base64 döner."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail(size, Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


async def _run(fn, *args) -> Any:
    """Sync fonksiyonu thread pool'da asenkron çalıştırır."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_POOL, fn, *args)


# ══════════════════════════════════════════════════════════════════
# ROUTE 1 – Tam Analiz (paralel)
# ══════════════════════════════════════════════════════════════════

@app.post(
    "/api/analyze",
    response_model=AnalysisResult,
    summary="Tüm analizleri paralel çalıştırır",
    tags=["Analiz"],
)
async def analyze_all(body: AnalyzeUrlRequest):
    """
    Verilen URL'deki görüntüyü **tüm yöntemlerle** paralel analiz eder.

    - `id` → .NET'ten gelir, yanıtta aynen döner
    - Model tahmini (simüle ResNet50) + Grad-CAM
    - ELA (Error Level Analysis)
    - FFT (Fast Fourier Transform)
    - Metadata / EXIF
    - Thumbnail
    """
    start = time.time()

    image_bytes = await _fetch_image(body.image_url)
    filename    = body.image_url.split("/")[-1].split("?")[0]

    results = await asyncio.gather(
        _run(simulate_model_prediction, image_bytes),
        _run(analyze_ela,               image_bytes),
        _run(analyze_fft,               image_bytes),
        _run(analyze_metadata,          image_bytes, filename),
        _run(_make_thumbnail_b64,       image_bytes),
        return_exceptions=True,
    )

    names = ["Model", "ELA", "FFT", "Metadata", "Thumbnail"]
    for name, res in zip(names, results):
        if isinstance(res, Exception):
            return JSONResponse(
                status_code=500,
                content=ErrorResponse(
                    Id=body.id,
                    ErrorMessage=f"{name} hatası: {res}",
                ).model_dump(mode="json"),
            )

    model_r, ela_r, fft_r, meta_r, thumb_b64 = results

    return AnalysisResult(
        Id=body.id,  # .NET'ten gelen ID aynen döner

        IsDeepfake    = model_r["is_deepfake"],
        CnnConfidence = model_r["confidence"],

        ElaScore        = ela_r["score"],
        FftAnomalyScore = fft_r["anomaly_score"],

        ExifHasMetadata          = meta_r["has_metadata"],
        ExifCameraInfo           = meta_r["camera_info"],
        ExifSuspiciousIndicators = ";".join(meta_r["suspicious_indicators"]) or None,

        GradcamImage   = model_r["gradcam_b64"],
        ElaImage       = ela_r["heatmap_b64"],
        FftImage       = fft_r["spectrum_b64"],
        ThumbnailImage = thumb_b64,

        ProcessingTimeSeconds = round(time.time() - start, 2),
        Status = "Completed",
    )


# ══════════════════════════════════════════════════════════════════
# ROUTE 2 – Sadece ELA
# ══════════════════════════════════════════════════════════════════

@app.post(
    "/api/ela",
    response_model=ElaResult,
    summary="Sadece ELA analizi",
    tags=["Analiz"],
)
async def route_ela(body: AnalyzeUrlRequest):
    """Error Level Analysis – manipülasyon bölgelerini tespit eder."""
    image_bytes = await _fetch_image(body.image_url)
    result      = await _run(analyze_ela, image_bytes)
    return ElaResult(id=body.id, **result)


# ══════════════════════════════════════════════════════════════════
# ROUTE 3 – Sadece FFT
# ══════════════════════════════════════════════════════════════════

@app.post(
    "/api/fft",
    response_model=FftResult,
    summary="Sadece FFT analizi",
    tags=["Analiz"],
)
async def route_fft(body: AnalyzeUrlRequest):
    """Fast Fourier Transform – frekans alanı anomali tespiti."""
    image_bytes = await _fetch_image(body.image_url)
    result      = await _run(analyze_fft, image_bytes)
    return FftResult(id=body.id, **result)


# ══════════════════════════════════════════════════════════════════
# ROUTE 4 – Sadece Metadata
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
# ROUTE 5 – Sadece Model
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
# ROUTE 6 – Health / Root
# ══════════════════════════════════════════════════════════════════

@app.get("/health", tags=["Sistem"])
async def health():
    return {
        "status":           "healthy",
        "version":          "3.0.0",
        "cpu_count":        _CPU,
        "thread_workers":   _POOL._max_workers,
        "disk_writes":      False,
        "api_key_enabled":  not API_KEY_DISABLED,
        "timestamp":        time.time(),
    }


@app.get("/", tags=["Sistem"])
async def root():
    return {
        "service":         "Deepfake Detection API",
        "version":         "3.0.0",
        "docs":            "/docs",
        "api_key_enabled": not API_KEY_DISABLED,
    }


# ── Shutdown ──────────────────────────────────────────────────────

@app.on_event("shutdown")
async def shutdown():
    _POOL.shutdown(wait=True)