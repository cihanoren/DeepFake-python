from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ══════════════════════════════════════════════════════════════════
# İSTEK MODELİ
# ══════════════════════════════════════════════════════════════════

class AnalyzeUrlRequest(BaseModel):
    """
    .NET API'den gelen analiz isteği.

    İş Akışı:
      1. Kullanıcı görseli .NET'e yükler
      2. .NET görseli diske kaydeder, DB'de 'Processing' kaydı açar
      3. Bu istek Python'a iletilir
      4. Python analiz yapar → base64 görseller + skorlar döner
      5. .NET base64'leri diske yazar, *Path alanlarını günceller
      6. .NET thumbnail oluşturur (150x150), ThumbnailPath yazar
      7. DB Status → 'Completed'
    """
    id:                  UUID = Field(..., description=".NET'in ürettiği kayıt UUID'si")
    image_url:           str  = Field(..., description="Görselin erişilebilir URL'si")

    class Config:
        json_schema_extra = {
            "example": {
                "id":                  "550e8400-e29b-41d4-a716-446655440000",
                "image_url":           "https://api.example.com/uploads/img123.jpg",
                
            }
        }


# ══════════════════════════════════════════════════════════════════
# ALT SONUÇ MODELLERİ (tekil route'lar)
# ══════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════
# ANA YANIT MODELİ  ←→  DB: AnalysisResults tablosu
# ══════════════════════════════════════════════════════════════════

class AnalysisResult(BaseModel):
    """
    Python servisi → .NET API yanıtı.

    DB Sütun Eşleşmesi:
    ┌─────────────────────────────┬──────────────────────────────────────┐
    │ Python Alanı                │ DB Sütunu / Açıklama                 │
    ├─────────────────────────────┼──────────────────────────────────────┤
    │ Id                          │ Id  (.NET'ten gelir, aynen döner)    │
    │ IsDeepfake                  │ IsDeepfake                           │
    │ CnnConfidence               │ CnnConfidence                        │
    │ ElaScore                    │ ElaScore                             │
    │ FftAnomalyScore             │ FftAnomalyScore                      │
    │ ExifHasMetadata             │ ExifHasMetadata                      │
    │ ExifCameraInfo              │ ExifCameraInfo                       │
    │ ExifSuspiciousIndicators    │ ExifSuspiciousIndicators             │
    │ GradcamImageBase64          │ → .NET diske yazar → GradcamImagePath│
    │ ElaImageBase64              │ → .NET diske yazar → ElaImagePath    │
    │ FftImageBase64              │ → .NET diske yazar → FftImagePath    │
    │ (yok)                       │ OriginalImagePath  (.NET biliyor)    │
    │ (yok)                       │ ThumbnailPath      (.NET oluşturur)  │
    │ ProcessingTimeSeconds       │ ProcessingTimeSeconds                │
    │ Status                      │ Status                               │
    │ ErrorMessage                │ ErrorMessage                         │
    │ CreatedAt / UpdatedAt       │ CreatedAt / UpdatedAt                │
    └─────────────────────────────┴──────────────────────────────────────┘
    """

    # Kimlik
    Id: UUID

    # CNN
    IsDeepfake:    bool
    CnnConfidence: float = Field(..., ge=0.0, le=1.0)

    # Analiz Skorları
    ElaScore:        Optional[float] = Field(None, ge=0.0, le=1.0)
    FftAnomalyScore: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Metadata
    ExifHasMetadata:          bool
    ExifCameraInfo:           Optional[str] = None
    ExifSuspiciousIndicators: Optional[str] = None  # ';' ile ayrılmış

    # Analiz Görselleri — base64 JPEG
    # .NET bunları diske yazıp DB'deki *Path sütunlarını günceller.
    # OriginalImagePath ve ThumbnailPath .NET tarafında yönetilir.
    GradcamImageBase64: Optional[str] = None
    ElaImageBase64:     Optional[str] = None
    FftImageBase64:     Optional[str] = None

    # İşlem Bilgisi
    ProcessingTimeSeconds: Optional[float] = None
    Status:       str           = "Completed"  # Processing | Completed | Failed
    ErrorMessage: Optional[str] = None

    # Zaman Damgaları
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
                "ExifSuspiciousIndicators": "EXIF verisi yok;Kamera bilgisi eksik",
                "GradcamImageBase64":       "<base64 JPEG — .NET GradcamImagePath'e yazar>",
                "ElaImageBase64":           "<base64 JPEG — .NET ElaImagePath'e yazar>",
                "FftImageBase64":           "<base64 JPEG — .NET FftImagePath'e yazar>",
                "ProcessingTimeSeconds":    3.45,
                "Status":                   "Completed",
                "ErrorMessage":             None,
            }
        }


# ══════════════════════════════════════════════════════════════════
# HATA YANIT MODELİ
# DB: Status='Failed', ErrorMessage doldurulur
# ══════════════════════════════════════════════════════════════════

class ErrorResponse(BaseModel):
    Id:           UUID
    Status:       str      = "Failed"
    ErrorMessage: str
    CreatedAt:    datetime = Field(default_factory=datetime.utcnow)