import os
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime
from typing import Dict, List

def analyze_metadata(image_path: str) -> Dict:
    """
    Metadata analizi yapar
    
    Returns:
        dict: {
            'has_metadata': bool,
            'camera_info': str or None,
            'suspicious_indicators': list,
            'exif_data': dict
        }
    """
    img = Image.open(image_path)
    exif_data = img.getexif()
    
    has_metadata = bool(exif_data)
    camera_info = None
    suspicious_indicators = []
    exif_dict = {}
    
    if not exif_data:
        suspicious_indicators.append("EXIF verisi yok")
    else:
        exif_dict = {TAGS.get(k, k): v for k, v in exif_data.items()}
        
        # Kamera bilgisi
        make = exif_dict.get('Make', '')
        model = exif_dict.get('Model', '')
        if make or model:
            camera_info = f"{make} {model}".strip()
        else:
            suspicious_indicators.append("Kamera bilgisi eksik")
        
        # Software kontrolü
        software_keywords = [
            'midjourney', 'dall-e', 'stable diffusion', 'ai', 
            'generator', 'synthetic', 'openai', 'comfyui'
        ]
        
        if 'Software' in exif_dict:
            software = str(exif_dict['Software']).lower()
            if any(kw in software for kw in software_keywords):
                suspicious_indicators.append(f"AI yazılımı: {exif_dict['Software']}")
        
        # Tarih kontrolü
        if 'DateTime' in exif_dict:
            try:
                dt = datetime.strptime(exif_dict['DateTime'], '%Y:%m:%d %H:%M:%S')
                if dt.year < 2000 or dt > datetime.now():
                    suspicious_indicators.append("Tarih anomalisi")
            except:
                pass
    
    # Dosya özellikleri
    file_size = os.stat(image_path).st_size
    
    if image_path.lower().endswith('.png') and exif_data:
        suspicious_indicators.append("PNG formatında EXIF")
    
    if file_size < 100 * 1024:
        suspicious_indicators.append("Küçük dosya boyutu")
    
    return {
        'has_metadata': has_metadata,
        'camera_info': camera_info,
        'suspicious_indicators': suspicious_indicators,
        'exif_data': exif_dict
    }