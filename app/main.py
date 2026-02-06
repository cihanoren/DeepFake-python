import os
import time
import shutil
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import Dict, Any
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from PIL import Image

from .config import *
from .models import AnalysisResult, ErrorResponse
from analysis import (
    analyze_ela,
    analyze_fft,
    analyze_metadata,
    simulate_model_prediction
)

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION
)

# Thread pool executor (I/O bound işlemler için)
thread_executor = ThreadPoolExecutor(max_workers=4)

# Process pool executor (CPU bound işlemler için - Mac'te daha verimli)
process_executor = ProcessPoolExecutor(max_workers=4)


def create_thumbnail(image_path: str, thumbnail_dir: str, size=(256, 256)) -> str:
    """Thumbnail oluşturur"""
    img = Image.open(image_path)
    img.thumbnail(size, Image.Resampling.LANCZOS)
    
    thumbnail_filename = f"thumb_{os.path.basename(image_path)}"
    thumbnail_path = os.path.join(thumbnail_dir, thumbnail_filename)
    img.save(thumbnail_path)
    
    return thumbnail_path


async def run_analysis_parallel(image_path: str) -> Dict[str, Any]:
    """
    Tüm analizleri paralel olarak çalıştırır
    
    Stratejik Gruplama:
    - Model + Grad-CAM: En uzun süren (GPU kullanabilir) -> Process Pool
    - ELA: Orta süre (CPU yoğun) -> Process Pool  
    - FFT: Orta süre (CPU yoğun) -> Process Pool
    - Metadata: Çok hızlı (I/O) -> Thread Pool
    - Thumbnail: Çok hızlı (I/O) -> Thread Pool
    """
    
    loop = asyncio.get_event_loop()
    
    # CPU-bound işlemler için process pool
    model_task = loop.run_in_executor(
        process_executor,
        simulate_model_prediction,
        str(image_path),
        str(GRADCAM_DIR)
    )
    
    ela_task = loop.run_in_executor(
        process_executor,
        analyze_ela,
        str(image_path),
        str(ELA_DIR)
    )
    
    fft_task = loop.run_in_executor(
        process_executor,
        analyze_fft,
        str(image_path),
        str(FFT_DIR)
    )
    
    # I/O-bound işlemler için thread pool
    metadata_task = loop.run_in_executor(
        thread_executor,
        analyze_metadata,
        str(image_path)
    )
    
    thumbnail_task = loop.run_in_executor(
        thread_executor,
        create_thumbnail,
        str(image_path),
        str(THUMBNAIL_DIR)
    )
    
    # Tüm işlemleri paralel çalıştır ve bekle
    print("⚡ Paralel analiz başlatıldı...")
    results = await asyncio.gather(
        model_task,
        ela_task,
        fft_task,
        metadata_task,
        thumbnail_task,
        return_exceptions=True  # Hata olursa devam et
    )
    
    # Hata kontrolü
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            task_names = ['Model', 'ELA', 'FFT', 'Metadata', 'Thumbnail']
            raise Exception(f"{task_names[i]} analizi başarısız: {str(result)}")
    
    model_result, ela_result, fft_result, metadata_result, thumbnail_path = results
    
    return {
        'model': model_result,
        'ela': ela_result,
        'fft': fft_result,
        'metadata': metadata_result,
        'thumbnail': thumbnail_path
    }


@app.get("/")
async def root():
    """API sağlık kontrolü"""
    return {
        "service": "Deepfake Detection API",
        "version": API_VERSION,
        "status": "running",
        "parallel_processing": True,
        "workers": {
            "thread_pool": thread_executor._max_workers,
            "process_pool": process_executor._max_workers
        }
    }


@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze_image(file: UploadFile = File(...)):
    """
    Görüntü analizi endpoint'i (Paralel İşleme)
    
    Tüm analizler eşzamanlı olarak çalıştırılır:
    - Model Prediction (simüle)
    - Error Level Analysis (ELA)
    - Fast Fourier Transform (FFT)
    - Metadata Analysis
    - Thumbnail Generation
    
    Returns:
        AnalysisResult: Tüm analiz sonuçları ve dosya yolları
    """
    start_time = time.time()
    temp_file_path = None
    
    try:
        # Dosya doğrulama
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Desteklenmeyen dosya formatı: {file_ext}"
            )
        
        # Dosyayı kaydet
        temp_file_path = UPLOAD_DIR / file.filename
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Dosya boyutu kontrolü
        file_size = os.path.getsize(temp_file_path)
        if file_size > MAX_FILE_SIZE:
            os.remove(temp_file_path)
            raise HTTPException(
                status_code=400,
                detail=f"Dosya çok büyük: {file_size / 1024 / 1024:.2f} MB (Max: 10 MB)"
            )
        
        print(f"📁 Dosya yüklendi: {file.filename} ({file_size / 1024:.1f} KB)")
        
        # PARALEL ANALİZ
        results = await run_analysis_parallel(temp_file_path)
        
        # İşlem süresi
        processing_time = time.time() - start_time
        
        # Sonuçları birleştir
        result = AnalysisResult(
            IsDeepfake=results['model']['is_deepfake'],
            CnnConfidence=results['model']['confidence'],
            
            ElaScore=results['ela']['score'],
            FftAnomalyScore=results['fft']['anomaly_score'],
            
            ExifHasMetadata=results['metadata']['has_metadata'],
            ExifCameraInfo=results['metadata']['camera_info'],
            ExifSuspiciousIndicators=';'.join(results['metadata']['suspicious_indicators']) 
                if results['metadata']['suspicious_indicators'] else None,
            
            OriginalImagePath=str(temp_file_path),
            GradcamImagePath=results['model']['gradcam_path'],
            ElaImagePath=results['ela']['heatmap_path'],
            FftImagePath=results['fft']['spectrum_path'],
            ThumbnailPath=results['thumbnail'],
            
            ProcessingTimeSeconds=round(processing_time, 2),
            Status="Completed"
        )
        
        print(f"✅ Analiz tamamlandı ({processing_time:.2f}s)")
        print(f"   └─ Model: {result.IsDeepfake} ({result.CnnConfidence:.2%})")
        print(f"   └─ ELA: {result.ElaScore:.4f}")
        print(f"   └─ FFT: {result.FftAnomalyScore:.4f}")
        
        return result
        
    except HTTPException:
        raise
        
    except Exception as e:
        print(f"❌ Hata: {str(e)}")
        
        # Hata durumunda geçici dosyayı temizle
        if temp_file_path and temp_file_path.exists():
            os.remove(temp_file_path)
        
        error_response = ErrorResponse(
            ErrorMessage=str(e)
        )
        
        return JSONResponse(
            status_code=500,
            content=error_response.model_dump(mode='json')
        )


@app.get("/health")
async def health_check():
    """Sağlık kontrolü endpoint'i"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "executors": {
            "thread_pool_active": thread_executor._threads is not None,
            "process_pool_active": process_executor._processes is not None
        }
    }


@app.on_event("shutdown")
async def shutdown_event():
    """Uygulama kapatılırken executor'ları temizle"""
    print("🔄 Executor'lar kapatılıyor...")
    thread_executor.shutdown(wait=True)
    process_executor.shutdown(wait=True)
    print("✅ Temizlik tamamlandı")

