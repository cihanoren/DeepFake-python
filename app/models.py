from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ── İstek Modelleri ───────────────────────────────────────────────

class AnalyzeUrlRequest(BaseModel):
    """
    Tüm analiz route'larının ortak istek modeli.
    `id` .NET tarafından üretilip gönderilir; Python tarafı asla UUID üretmez.
    """
    id:        UUID = Field(..., description=".NET tarafından üretilen kayıt UUID'si")
    image_url: str  = Field(..., description="Analiz edilecek görüntünün URL'si")

    class Config:
        json_schema_extra = {
            "example": {
                "id":        "550e8400-e29b-41d4-a716-446655440000",
                "image_url": "https://example.com/photo.jpg",
            }
        }


# ── Alt Sonuç Modelleri ───────────────────────────────────────────

class ElaMetrics(BaseModel):
    homogeneity:       float
    regional_variance: float
    edge_density:      float


class ElaResult(BaseModel):
    id:          UUID
    score:       float
    heatmap_b64: str
    metrics:     ElaMetrics


class FftMetrics(BaseModel):
    high_freq_ratio:     float
    center_intensity:    float
    spectral_smoothness: float


class FftResult(BaseModel):
    id:            UUID
    anomaly_score: float
    spectrum_b64:  str
    metrics:       FftMetrics


class MetadataResult(BaseModel):
    id:                    UUID
    has_metadata:          bool
    camera_info:           Optional[str]
    suspicious_indicators: List[str]


class ModelResult(BaseModel):
    id:          UUID
    is_deepfake: bool
    confidence:  float
    gradcam_b64: str


# ── Ana Yanıt Modeli (DB tablosuna uyumlu) ────────────────────────

class AnalysisResult(BaseModel):
    """
    .NET AnalysisResults tablosuna birebir uyumlu model.
    Id her zaman .NET'ten gelir, Python üretmez.
    Görseller base64 JPEG olarak taşınır, diske yazılmaz.
    """
    Id: UUID  # .NET'ten gelen, değişmez

    # CNN
    IsDeepfake:    bool
    CnnConfidence: float = Field(..., ge=0.0, le=1.0)

    # Analiz skorları
    ElaScore:        Optional[float] = Field(None, ge=0.0, le=1.0)
    FftAnomalyScore: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Metadata
    ExifHasMetadata:          bool
    ExifCameraInfo:           Optional[str] = None
    ExifSuspiciousIndicators: Optional[str] = None  # ';' ile ayrılmış

    # Görseller (base64 JPEG)
    GradcamImage:   Optional[str] = None
    ElaImage:       Optional[str] = None
    FftImage:       Optional[str] = None
    ThumbnailImage: Optional[str] = None

    # İşlem bilgisi
    ProcessingTimeSeconds: Optional[float] = None
    Status:       str           = "Completed"
    ErrorMessage: Optional[str] = None

    CreatedAt: datetime = Field(default_factory=datetime.utcnow)
    UpdatedAt: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "Id":                       "550e8400-e29b-41d4-a716-446655440000",
                "IsDeepfake":               True,
                "CnnConfidence":            0.8756,
                "ElaScore":                 0.6234,
                "FftAnomalyScore":          0.7123,
                "ExifHasMetadata":          False,
                "ExifCameraInfo":           None,
                "ExifSuspiciousIndicators": "EXIF verisi yok;Küçük dosya boyutu",
                "GradcamImage":             "<base64>",
                "ElaImage":                 "<base64>",
                "FftImage":                 "<base64>",
                "ThumbnailImage":           "<base64>",
                "ProcessingTimeSeconds":    3.45,
                "Status":                   "Completed",
            }
        }


# ── Hata Yanıt Modeli ─────────────────────────────────────────────

class ErrorResponse(BaseModel):
    Id:           UUID
    Status:       str      = "Failed"
    ErrorMessage: str
    CreatedAt:    datetime = Field(default_factory=datetime.utcnow)