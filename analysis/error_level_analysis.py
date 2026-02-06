import os
import tempfile
import numpy as np
import cv2
from PIL import Image, ImageChops
from typing import Dict, Tuple

def analyze_ela(image_path: str, output_dir: str) -> Dict:
    """
    ELA Analizi yapar ve sonuçları döner
    
    Returns:
        dict: {
            'score': float (0-1),
            'heatmap_path': str,
            'metrics': dict
        }
    """
    original = Image.open(image_path).convert("RGB")
    
    qualities = [75, 85, 95]
    ela_maps = []
    
    for q in qualities:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            original.save(tmp.name, "JPEG", quality=q)
            compressed = Image.open(tmp.name).convert("RGB")
            
            diff = ImageChops.difference(original, compressed)
            diff_np = np.array(diff)
            
            normalized = cv2.normalize(diff_np, None, 0, 255, cv2.NORM_MINMAX)
            ela_maps.append(normalized)
            os.remove(tmp.name)
    
    final_ela = np.mean(ela_maps, axis=0).astype(np.uint8)
    gray_ela = cv2.cvtColor(final_ela, cv2.COLOR_RGB2GRAY)
    
    # Metrikler
    homogeneity = 1 - (np.std(gray_ela) / (np.mean(gray_ela) + 1e-5))
    
    h, w = gray_ela.shape
    grid_size = 32
    variances = []
    
    for i in range(0, h, grid_size):
        for j in range(0, w, grid_size):
            block = gray_ela[i:i+grid_size, j:j+grid_size]
            if block.size > 0:
                variances.append(np.var(block))
    
    regional_variance = np.std(variances) if variances else 0
    
    edges = cv2.Canny(gray_ela, 50, 150)
    edge_density = np.sum(edges > 0) / edges.size
    
    # Skor hesaplama (0-100 -> 0-1)
    manipulation_score = 0
    if homogeneity < 0.3:
        manipulation_score += 35
    if regional_variance > 50:
        manipulation_score += 40
    if edge_density > 0.15:
        manipulation_score += 25
    
    normalized_score = manipulation_score / 100.0
    
    # Heatmap kaydet
    heatmap = cv2.applyColorMap(gray_ela, cv2.COLORMAP_JET)
    heatmap_filename = f"ela_{os.path.basename(image_path)}"
    heatmap_path = os.path.join(output_dir, heatmap_filename)
    cv2.imwrite(heatmap_path, heatmap)
    
    return {
        'score': round(normalized_score, 4),
        'heatmap_path': heatmap_path,
        'metrics': {
            'homogeneity': round(homogeneity, 3),
            'regional_variance': round(regional_variance, 2),
            'edge_density': round(edge_density, 3)
        }
    }