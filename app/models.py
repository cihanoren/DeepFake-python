from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID, uuid4

class AnalysisRequest(BaseModel):
    """Analiz isteği modeli"""
    image_path: str = Field(..., description="Analiz edilecek görüntünün dosya yolu")

class AnalysisResult(BaseModel):
    """
    .NET API'deki AnalysisResults tablosuna uyumlu model
    """
    Id: UUID = Field(default_factory=uuid4)
    IsDeepfake: bool
    CnnConfidence: float = Field(..., ge=0.0, le=1.0)
    
    ElaScore: Optional[float] = Field(None, ge=0.0, le=1.0)
    FftAnomalyScore: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    ExifHasMetadata: bool
    ExifCameraInfo: Optional[str] = None
    ExifSuspiciousIndicators: Optional[str] = None
    
    OriginalImagePath: str
    GradcamImagePath: Optional[str] = None
    ElaImagePath: Optional[str] = None
    FftImagePath: Optional[str] = None
    ThumbnailPath: Optional[str] = None
    
    ProcessingTimeSeconds: Optional[float] = None
    Status: str = "Completed"
    ErrorMessage: Optional[str] = None
    
    CreatedAt: datetime = Field(default_factory=datetime.utcnow)
    UpdatedAt: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "Id": "550e8400-e29b-41d4-a716-446655440000",
                "IsDeepfake": True,
                "CnnConfidence": 0.8756,
                "ElaScore": 0.6234,
                "FftAnomalyScore": 0.7123,
                "ExifHasMetadata": False,
                "ExifCameraInfo": None,
                "ExifSuspiciousIndicators": "EXIF verisi yok;Küçük dosya boyutu",
                "OriginalImagePath": "/uploads/image123.jpg",
                "GradcamImagePath": "/outputs/gradcam/gradcam_image123.jpg",
                "ElaImagePath": "/outputs/ela/ela_image123.jpg",
                "FftImagePath": "/outputs/fft/fft_image123.jpg",
                "ThumbnailPath": "/outputs/thumbnails/thumb_image123.jpg",
                "ProcessingTimeSeconds": 3.45,
                "Status": "Completed"
            }
        }

class ErrorResponse(BaseModel):
    """Hata cevabı modeli"""
    Id: UUID = Field(default_factory=uuid4)
    Status: str = "Failed"
    ErrorMessage: str
    CreatedAt: datetime = Field(default_factory=datetime.utcnow)