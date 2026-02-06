# =============================================================================
# DEEPFAKE DETECTION - FORENSIC ANALYSIS TOOLKIT
# Author: Ali Köroğlu
# =============================================================================

import os
import tempfile
import numpy as np
import cv2
from PIL import Image, ImageChops
from PIL.ExifTags import TAGS
from datetime import datetime

# =============================================================================
# 1. ERROR LEVEL ANALYSIS (ELA)
# =============================================================================

def analyze_ela(image_path):
    """
    ELA Analizi - JPEG manipülasyon tespiti
    
    TESPİT KRİTERLERİ:
    - Homojenlik Skoru < 0.3  → Şüpheli
    - Bölgesel Varyans > 50   → Manipülasyon olası
    - Edge Consistency < 0.6  → Anomali
    """
    original = Image.open(image_path).convert("RGB")
    
    # Çoklu kalite seviyesi analizi
    qualities = [75, 85, 95]
    ela_maps = []
    
    for q in qualities:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            original.save(tmp.name, "JPEG", quality=q)
            compressed = Image.open(tmp.name).convert("RGB")
            
            diff = ImageChops.difference(original, compressed)
            diff_np = np.array(diff)
            
            # Normalize (0-255)
            normalized = cv2.normalize(diff_np, None, 0, 255, cv2.NORM_MINMAX)
            ela_maps.append(normalized)
            os.remove(tmp.name)
    
    # Ortalama ELA haritası
    final_ela = np.mean(ela_maps, axis=0).astype(np.uint8)
    
    # KRİTERLER HESAPLAMA
    # 1. Homojenlik (tüm görüntüde benzer mi?)
    gray_ela = cv2.cvtColor(final_ela, cv2.COLOR_RGB2GRAY)
    homogeneity = 1 - (np.std(gray_ela) / (np.mean(gray_ela) + 1e-5))
    
    # 2. Bölgesel Varyans (grid tabanlı)
    h, w = gray_ela.shape
    grid_size = 32
    variances = []
    
    for i in range(0, h, grid_size):
        for j in range(0, w, grid_size):
            block = gray_ela[i:i+grid_size, j:j+grid_size]
            if block.size > 0:
                variances.append(np.var(block))
    
    regional_variance = np.std(variances) if variances else 0
    
    # 3. Edge Consistency (kenarlar tutarlı mı?)
    edges = cv2.Canny(gray_ela, 50, 150)
    edge_density = np.sum(edges > 0) / edges.size
    
    # SKOR HESAPLAMA (0-100)
    manipulation_score = 0
    
    if homogeneity < 0.3:
        manipulation_score += 35
    if regional_variance > 50:
        manipulation_score += 40
    if edge_density > 0.15:  # Çok fazla ELA kenarı
        manipulation_score += 25
    
    # Görselleştirme
    heatmap = cv2.applyColorMap(gray_ela, cv2.COLORMAP_JET)
    
    return {
        'ela_map': final_ela,
        'heatmap': heatmap,
        'manipulation_score': manipulation_score,
        'metrics': {
            'homogeneity': round(homogeneity, 3),
            'regional_variance': round(regional_variance, 2),
            'edge_density': round(edge_density, 3)
        }
    }


# =============================================================================
# 2. FAST FOURIER TRANSFORM (FFT) ANALYSIS
# =============================================================================

def analyze_fft(image_path):
    """
    FFT Analizi - Frekans alanı anomali tespiti
    
    TESPİT KRİTERLERİ:
    - Yüksek Frekans Oranı > 0.4 → AI üretimi olası
    - Merkez Yoğunluğu > 0.7      → Doğal olmayan dağılım
    - Spektral Düzgünlük < 0.25   → Sentetik görüntü
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    
    # FFT hesaplama
    f_transform = np.fft.fft2(img)
    f_shift = np.fft.fftshift(f_transform)
    magnitude = np.abs(f_shift)
    
    # Log transform (görselleştirme için)
    magnitude_log = np.log1p(magnitude)
    
    # KRİTERLER HESAPLAMA
    h, w = magnitude.shape
    center_y, center_x = h // 2, w // 2
    
    # 1. Yüksek Frekans Oranı
    radius = min(h, w) // 4
    y, x = np.ogrid[:h, :w]
    mask_low = (x - center_x)**2 + (y - center_y)**2 <= radius**2
    
    low_freq_energy = np.sum(magnitude[mask_low])
    total_energy = np.sum(magnitude)
    high_freq_ratio = 1 - (low_freq_energy / total_energy)
    
    # 2. Merkez Yoğunluğu
    center_region = magnitude[
        center_y-radius:center_y+radius,
        center_x-radius:center_x+radius
    ]
    center_intensity = np.mean(center_region) / (np.mean(magnitude) + 1e-5)
    
    # 3. Spektral Düzgünlük
    distances = np.sqrt((x - center_x)**2 + (y - center_y)**2).astype(int)
    radial_profile = []
    
    for r in range(1, min(h, w) // 2):
        mask = (distances == r)
        if np.sum(mask) > 0:
            radial_profile.append(np.mean(magnitude[mask]))
    
    spectral_smoothness = np.std(radial_profile) / (np.mean(radial_profile) + 1e-5)
    
    # SKOR HESAPLAMA
    ai_score = 0
    
    if high_freq_ratio > 0.4:
        ai_score += 30
    if center_intensity > 0.7:
        ai_score += 45
    if spectral_smoothness < 0.25:
        ai_score += 25
    
    # Görselleştirme
    spectrum_vis = cv2.normalize(magnitude_log, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    spectrum_colored = cv2.applyColorMap(spectrum_vis, cv2.COLORMAP_VIRIDIS)
    
    return {
        'spectrum': spectrum_colored,
        'ai_score': ai_score,
        'metrics': {
            'high_freq_ratio': round(high_freq_ratio, 3),
            'center_intensity': round(center_intensity, 3),
            'spectral_smoothness': round(spectral_smoothness, 3)
        }
    }


# =============================================================================
# 3. METADATA ANALYSIS
# =============================================================================

def analyze_metadata(image_path):
    """
    Metadata Analizi - EXIF ve dosya bilgisi kontrolü
    """
    img = Image.open(image_path)
    
    suspicious_score = 0
    flags = []
    exif_dict = {}
    
    # EXIF verisi var mı?
    exif_data = img.getexif()
    
    if not exif_data:
        suspicious_score += 40
        flags.append("EXIF verisi yok (AI üretimi veya temizlenmiş)")
    else:
        exif_dict = {TAGS.get(k, k): v for k, v in exif_data.items()}
        
        # Software kontrolü
        software_keywords = [
            'midjourney', 'dall-e', 'stable diffusion', 'ai', 
            'generator', 'synthetic', 'openai', 'comfyui'
        ]
        
        if 'Software' in exif_dict:
            software = str(exif_dict['Software']).lower()
            if any(kw in software for kw in software_keywords):
                suspicious_score += 50
                flags.append(f"AI yazılımı tespit edildi: {exif_dict['Software']}")
        
        # Kamera modeli kontrolü
        if 'Model' not in exif_dict and 'Make' not in exif_dict:
            suspicious_score += 25
            flags.append("Kamera bilgisi eksik")
        
        # Tarih tutarlılığı
        if 'DateTime' in exif_dict:
            try:
                dt = datetime.strptime(exif_dict['DateTime'], '%Y:%m:%d %H:%M:%S')
                if dt.year < 2000 or dt > datetime.now():
                    suspicious_score += 20
                    flags.append("Tarih anomalisi tespit edildi")
            except:
                pass
    
    # Dosya özellikleri
    file_stats = os.stat(image_path)
    file_size = file_stats.st_size
    
    # PNG ama EXIF var (şüpheli)
    if image_path.lower().endswith('.png') and exif_data:
        suspicious_score += 15
        flags.append("PNG formatında EXIF (olağandışı)")
    
    # Çok küçük dosya boyutu
    if file_size < 100 * 1024:  # 100 KB
        suspicious_score += 10
        flags.append("Olağandışı küçük dosya boyutu")
    
    return {
        'suspicious_score': min(suspicious_score, 100),
        'flags': flags,
        'exif_data': exif_dict if exif_data else None,
        'file_size_kb': round(file_size / 1024, 2)
    }


# =============================================================================
# 4. GRAD-CAM (Model gerektirir - opsiyonel)
# =============================================================================

def generate_gradcam(model, image_path, last_conv_layer_name='conv5_block3_out'):
    """
    Grad-CAM - Model açıklanabilirliği
    NOT: TensorFlow gerektirir, model eğitimi sonrası kullanılır
    """
    try:
        import tensorflow as tf
        from tensorflow.keras.models import Model as KerasModel
        
        # Görüntü ön işleme
        img = tf.keras.preprocessing.image.load_img(image_path, target_size=(224, 224))
        img_array = tf.keras.preprocessing.image.img_to_array(img)
        img_array = np.expand_dims(img_array, axis=0)
        img_array = tf.keras.applications.resnet50.preprocess_input(img_array)
        
        # Grad-CAM hesaplama
        grad_model = KerasModel(
            inputs=model.input,
            outputs=[model.get_layer(last_conv_layer_name).output, model.output]
        )
        
        with tf.GradientTape() as tape:
            conv_outputs, predictions = grad_model(img_array)
            class_idx = tf.argmax(predictions[0])
            class_output = predictions[:, class_idx]
        
        # Gradyanlar
        grads = tape.gradient(class_output, conv_outputs)
        pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))
        
        # Heatmap
        conv_outputs = conv_outputs[0]
        heatmap = conv_outputs @ pooled_grads[..., tf.newaxis]
        heatmap = tf.squeeze(heatmap)
        heatmap = tf.maximum(heatmap, 0) / tf.math.reduce_max(heatmap)
        heatmap = heatmap.numpy()
        
        # Görselleştirme
        heatmap_resized = cv2.resize(heatmap, (img.width, img.height))
        heatmap_colored = cv2.applyColorMap(
            np.uint8(255 * heatmap_resized), 
            cv2.COLORMAP_JET
        )
        
        # Orijinal görüntü üzerine bindirme
        original = cv2.imread(image_path)
        original = cv2.resize(original, (img.width, img.height))
        superimposed = cv2.addWeighted(original, 0.6, heatmap_colored, 0.4, 0)
        
        return {
            'heatmap': heatmap_colored,
            'superimposed': superimposed,
            'prediction_class': int(class_idx.numpy()),
            'confidence': float(predictions[0][class_idx])
        }
    except ImportError:
        print("⚠️  TensorFlow yüklü değil. Grad-CAM atlanıyor.")
        return None


# =============================================================================
# 5. COMPREHENSIVE ANALYSIS
# =============================================================================

def comprehensive_analysis(image_path, model=None):
    """
    Tüm analizleri birleştiren ana fonksiyon
    """
    print(f"\n{'='*60}")
    print(f"  DEEPFAKE DETECTION - FORENSIC ANALYSIS")
    print(f"{'='*60}\n")
    print(f"📁 Analiz edilen dosya: {os.path.basename(image_path)}\n")
    
    results = {}
    
    # 1. ELA Analizi
    print("🔍 [1/3] ELA analizi yapılıyor...")
    results['ela'] = analyze_ela(image_path)
    print(f"    ✓ Manipülasyon Skoru: {results['ela']['manipulation_score']}/100")
    
    # 2. FFT Analizi
    print("🔍 [2/3] FFT analizi yapılıyor...")
    results['fft'] = analyze_fft(image_path)
    print(f"    ✓ AI Skoru: {results['fft']['ai_score']}/100")
    
    # 3. Metadata Analizi
    print("🔍 [3/3] Metadata analizi yapılıyor...")
    results['metadata'] = analyze_metadata(image_path)
    print(f"    ✓ Şüpheli Skor: {results['metadata']['suspicious_score']}/100")
    
    # 4. Model Tahmini (varsa)
    if model:
        print("\n🤖 Model tahmini yapılıyor...")
        results['gradcam'] = generate_gradcam(model, image_path)
    
    # GENEL SKOR HESAPLAMA
    weights = {
        'ela': 0.25,
        'fft': 0.30,
        'metadata': 0.20,
        'model': 0.25
    }
    
    final_score = (
        results['ela']['manipulation_score'] * weights['ela'] +
        results['fft']['ai_score'] * weights['fft'] +
        results['metadata']['suspicious_score'] * weights['metadata']
    )
    
    if model and results.get('gradcam'):
        model_score = 100 if results['gradcam']['prediction_class'] == 1 else 0
        final_score += model_score * results['gradcam']['confidence'] * weights['model']
    
    # Karar
    if final_score < 30:
        verdict = "✅ GERÇEK (Real)"
        confidence = "Yüksek"
        color = "\033[92m"  # Yeşil
    elif final_score < 60:
        verdict = "⚠️  BELİRSİZ (Uncertain)"
        confidence = "Orta - Uzman incelemesi önerilir"
        color = "\033[93m"  # Sarı
    else:
        verdict = "❌ SAHTEKARLı (Fake/AI Generated)"
        confidence = "Yüksek"
        color = "\033[91m"  # Kırmızı
    
    results['final'] = {
        'score': round(final_score, 2),
        'verdict': verdict,
        'confidence': confidence
    }
    
    # Sonuçları yazdır
    print(f"\n{'='*60}")
    print(f"{color}  SONUÇ: {verdict}\033[0m")
    print(f"  Güven Seviyesi: {confidence}")
    print(f"  Genel Skor: {results['final']['score']}/100")
    print(f"{'='*60}\n")
    
    return results


# =============================================================================
# 6. HTML REPORT GENERATOR
# =============================================================================

def generate_report(results, output_path='analysis_report.html'):
    """
    HTML formatında detaylı rapor üretir
    """
    html = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <title>Deepfake Analiz Raporu</title>
        <style>
            body {{
                font-family: 'Segoe UI', Arial, sans-serif;
                max-width: 900px;
                margin: 40px auto;
                padding: 20px;
                background: #f5f5f5;
            }}
            .container {{
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
            }}
            h2 {{
                color: #34495e;
                margin-top: 30px;
            }}
            .score-box {{
                background: #ecf0f1;
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
                text-align: center;
            }}
            .score {{
                font-size: 48px;
                font-weight: bold;
                color: #e74c3c;
            }}
            .verdict {{
                font-size: 24px;
                margin: 10px 0;
            }}
            ul {{
                line-height: 1.8;
            }}
            .metric {{
                background: #f8f9fa;
                padding: 10px;
                margin: 5px 0;
                border-left: 4px solid #3498db;
            }}
            .warning {{
                background: #fff3cd;
                border: 1px solid #ffc107;
                padding: 15px;
                border-radius: 5px;
                margin-top: 30px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔍 Deepfake Tespit Analiz Raporu</h1>
            
            <div class="score-box">
                <div class="verdict">{results['final']['verdict']}</div>
                <div class="score">{results['final']['score']}/100</div>
                <p><strong>Güven Seviyesi:</strong> {results['final']['confidence']}</p>
            </div>
            
            <h2>1. 📊 Error Level Analysis (ELA)</h2>
            <p><strong>Manipülasyon Skoru:</strong> {results['ela']['manipulation_score']}/100</p>
            <div class="metric">
                <strong>Homojenlik:</strong> {results['ela']['metrics']['homogeneity']}<br>
                <strong>Bölgesel Varyans:</strong> {results['ela']['metrics']['regional_variance']}<br>
                <strong>Kenar Yoğunluğu:</strong> {results['ela']['metrics']['edge_density']}
            </div>
            
            <h2>2. 📈 Fast Fourier Transform (FFT) Analizi</h2>
            <p><strong>AI Skoru:</strong> {results['fft']['ai_score']}/100</p>
            <div class="metric">
                <strong>Yüksek Frekans Oranı:</strong> {results['fft']['metrics']['high_freq_ratio']}<br>
                <strong>Merkez Yoğunluğu:</strong> {results['fft']['metrics']['center_intensity']}<br>
                <strong>Spektral Düzgünlük:</strong> {results['fft']['metrics']['spectral_smoothness']}
            </div>
            
            <h2>3. 📄 Metadata Analizi</h2>
            <p><strong>Şüpheli Skor:</strong> {results['metadata']['suspicious_score']}/100</p>
            <p><strong>Dosya Boyutu:</strong> {results['metadata']['file_size_kb']} KB</p>
            <p><strong>Tespit Edilen Anomaliler:</strong></p>
            <ul>
                {''.join(f'<li>{flag}</li>' for flag in results['metadata']['flags']) if results['metadata']['flags'] else '<li>Anomali tespit edilmedi</li>'}
            </ul>
            
            <div class="warning">
                <strong>⚠️  Yasal Uyarı:</strong><br>
                Bu sistem bir karar destek aracıdır ve hukuki veya kesin doğrulama 
                aracı olarak kullanılamaz. Sonuçlar uzman değerlendirmesi ile 
                desteklenmelidir.
            </div>
        </div>
    </body>
    </html>
    """
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"📄 Rapor oluşturuldu: {output_path}")
    return output_path


# =============================================================================
# 7. MAIN - TEST KISMI
# =============================================================================

if __name__ == "__main__":
    # Test edilecek görüntü
    image_path = "manzara.jpeg"  # Kendi dosyanızı buraya yazın
    
    # Dosya var mı kontrol
    if not os.path.exists(image_path):
        print(f"❌ Hata: '{image_path}' dosyası bulunamadı!")
        print("Lütfen geçerli bir görüntü dosyası yolu girin.")
        exit(1)
    
    # Analizleri çalıştır
    results = comprehensive_analysis(image_path, model=None)
    
    # HTML rapor oluştur
    generate_report(results)
    
    # Görselleri kaydet (opsiyonel)
    cv2.imwrite('output_ela_heatmap.jpg', results['ela']['heatmap'])
    cv2.imwrite('output_fft_spectrum.jpg', results['fft']['spectrum'])
    
    print("\n✅ Analiz tamamlandı!")
    print("📊 Görsel çıktılar:")
    print("   - output_ela_heatmap.jpg")
    print("   - output_fft_spectrum.jpg")
    print("   - analysis_report.html")