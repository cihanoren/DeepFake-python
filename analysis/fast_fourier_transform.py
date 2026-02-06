import os
import numpy as np
import cv2
from typing import Dict

def analyze_fft(image_path: str, output_dir: str) -> Dict:
    """
    FFT Analizi yapar
    
    Returns:
        dict: {
            'anomaly_score': float (0-1),
            'spectrum_path': str,
            'metrics': dict
        }
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    
    # FFT hesaplama
    f_transform = np.fft.fft2(img)
    f_shift = np.fft.fftshift(f_transform)
    magnitude = np.abs(f_shift)
    magnitude_log = np.log1p(magnitude)
    
    h, w = magnitude.shape
    center_y, center_x = h // 2, w // 2
    radius = min(h, w) // 4
    
    y, x = np.ogrid[:h, :w]
    mask_low = (x - center_x)**2 + (y - center_y)**2 <= radius**2
    
    low_freq_energy = np.sum(magnitude[mask_low])
    total_energy = np.sum(magnitude)
    high_freq_ratio = 1 - (low_freq_energy / total_energy)
    
    center_region = magnitude[
        center_y-radius:center_y+radius,
        center_x-radius:center_x+radius
    ]
    center_intensity = np.mean(center_region) / (np.mean(magnitude) + 1e-5)
    
    distances = np.sqrt((x - center_x)**2 + (y - center_y)**2).astype(int)
    radial_profile = []
    
    for r in range(1, min(h, w) // 2):
        mask = (distances == r)
        if np.sum(mask) > 0:
            radial_profile.append(np.mean(magnitude[mask]))
    
    spectral_smoothness = np.std(radial_profile) / (np.mean(radial_profile) + 1e-5)
    
    # Skor hesaplama
    ai_score = 0
    if high_freq_ratio > 0.4:
        ai_score += 30
    if center_intensity > 0.7:
        ai_score += 45
    if spectral_smoothness < 0.25:
        ai_score += 25
    
    normalized_score = ai_score / 100.0
    
    # Spektrum görselleştirme
    spectrum_vis = cv2.normalize(magnitude_log, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    spectrum_colored = cv2.applyColorMap(spectrum_vis, cv2.COLORMAP_VIRIDIS)
    
    spectrum_filename = f"fft_{os.path.basename(image_path)}"
    spectrum_path = os.path.join(output_dir, spectrum_filename)
    cv2.imwrite(spectrum_path, spectrum_colored)
    
    return {
        'anomaly_score': round(normalized_score, 4),
        'spectrum_path': spectrum_path,
        'metrics': {
            'high_freq_ratio': round(high_freq_ratio, 3),
            'center_intensity': round(center_intensity, 3),
            'spectral_smoothness': round(spectral_smoothness, 3)
        }
    }