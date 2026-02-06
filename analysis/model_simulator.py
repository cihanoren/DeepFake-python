import numpy as np
import cv2
import os
from typing import Dict

def simulate_model_prediction(image_path: str, output_dir: str) -> Dict:
    """
    Model tahminini simüle eder (gerçek model eğitilene kadar)
    
    Basit kurallarla deepfake olasılığını tahmin eder:
    - Çok düzgün görüntüler -> Yüksek AI olasılığı
    - Gürültü az -> Yüksek AI olasılığı
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    
    # Basit metrikler
    noise = cv2.Laplacian(img, cv2.CV_64F).var()
    smoothness = np.std(img)
    
    # Simüle edilmiş tahmin
    # Düşük gürültü + yüksek düzgünlük = AI olasılığı
    if noise < 100 or smoothness < 30:
        is_deepfake = True
        confidence = 0.75 + np.random.uniform(0, 0.20)  # 0.75-0.95
    else:
        is_deepfake = False
        confidence = 0.65 + np.random.uniform(0, 0.30)  # 0.65-0.95
    
    # Grad-CAM simülasyonu (rastgele ısı haritası)
    h, w = img.shape
    heatmap = np.random.rand(h, w).astype(np.float32)
    heatmap = cv2.GaussianBlur(heatmap, (51, 51), 0)
    heatmap = (heatmap - heatmap.min()) / (heatmap.max() - heatmap.min())
    
    heatmap_colored = cv2.applyColorMap(
        np.uint8(255 * heatmap), 
        cv2.COLORMAP_JET
    )
    
    original = cv2.imread(image_path)
    original_resized = cv2.resize(original, (w, h))
    superimposed = cv2.addWeighted(original_resized, 0.6, heatmap_colored, 0.4, 0)
    
    gradcam_filename = f"gradcam_{os.path.basename(image_path)}"
    gradcam_path = os.path.join(output_dir, gradcam_filename)
    cv2.imwrite(gradcam_path, superimposed)
    
    return {
        'is_deepfake': is_deepfake,
        'confidence': round(float(confidence), 4),
        'gradcam_path': gradcam_path
    }