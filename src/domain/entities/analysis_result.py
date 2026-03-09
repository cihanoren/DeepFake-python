"""
Domain Entity: AnalysisResult
================================
Tüm analiz modüllerinin birleşik çıktısını temsil eder.
.NET DB şemasıyla birebir eşleşir.
Hiçbir dış katmana bağımlı değildir.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AnalysisStatus(str, Enum):
    COMPLETED = "Completed"
    FAILED    = "Failed"


@dataclass
class ElaMetrics:
    score:             float
    heatmap_b64:       str
    homogeneity:       float
    regional_variance: float
    edge_density:      float


@dataclass
class FftMetrics:
    anomaly_score:       float
    spectrum_b64:        str
    high_freq_ratio:     float
    center_intensity:    float
    spectral_smoothness: float


@dataclass
class ModelMetrics:
    is_deepfake:  bool
    confidence:   float
    gradcam_b64:  str


@dataclass
class MetadataMetrics:
    has_metadata:          bool
    camera_info:           Optional[str]
    suspicious_indicators: list[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """
    Başarılı bir analizin tam sonucunu taşır.
    to_dict() → result_queue'ya gönderilecek JSON payload'unu üretir.
    """
    record_id:              str
    model:                  ModelMetrics
    ela:                    ElaMetrics
    fft:                    FftMetrics
    meta:                   MetadataMetrics
    processing_time_seconds: float
    status:                 AnalysisStatus = AnalysisStatus.COMPLETED

    def to_dict(self) -> dict:
        """
        .NET AnalysisResult DB modeli ile birebir eşleşen payload.
        result_queue'ya JSON olarak yayınlanır.
        """
        return {
            "Id":              self.record_id,
            "IsDeepfake":      self.model.is_deepfake,
            "CnnConfidence":   self.model.confidence,

            "ElaScore":        self.ela.score,
            "FftAnomalyScore": self.fft.anomaly_score,

            "ExifHasMetadata":          self.meta.has_metadata,
            "ExifCameraInfo":           self.meta.camera_info,
            "ExifSuspiciousIndicators": (
                ";".join(self.meta.suspicious_indicators)
                if self.meta.suspicious_indicators else None
            ),

            "GradcamImageBase64": self.model.gradcam_b64,
            "ElaImageBase64":     self.ela.heatmap_b64,
            "FftImageBase64":     self.fft.spectrum_b64,

            "ProcessingTimeSeconds": self.processing_time_seconds,
            "Status":       self.status.value,
            "ErrorMessage": None,
        }


@dataclass
class FailedAnalysisResult:
    """
    Hata durumunda result_queue'ya gönderilir.
    .NET, DB'deki kaydı 'Failed' olarak işaretler.
    """
    record_id:     str
    error_message: str
    status:        AnalysisStatus = AnalysisStatus.FAILED

    def to_dict(self) -> dict:
        return {
            "Id":           self.record_id,
            "Status":       self.status.value,
            "ErrorMessage": self.error_message,
        }
