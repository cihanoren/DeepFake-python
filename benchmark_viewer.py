"""
Benchmark Viewer
================
API'yi çağırır, base64 görselleri alır ve browser'da açılan
interaktif bir HTML raporu üretir.

Kullanım:
    python3 benchmark_viewer.py
    python3 benchmark_viewer.py --url https://... --key your-key
"""

import time
import argparse
import uuid
import json
import base64
import webbrowser
import os
import requests
from datetime import datetime

API_BASE      = "http://localhost:8000"
DEFAULT_URL   = (
    "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEgI8hbyGkUDAF7hItsu4gTbLgrcM7YJLvTEL494jT4TR_fK3YKb9FRiWd0ZZOWUFFB20ZsAkGAYDvcxR5d9WC7WTy29BnOCobwqhNlfSaDjam8POajCwHVRIJaC9pitYr9Zu1x4h30uWEbE/s1600/The_Last_Supper_Jacopo_Bassano_1542.jpg"
)
DEFAULT_KEY   = "dev-secret-key-change-me"
OUTPUT_FILE   = "analysis_result.html"


# ── API Çağrısı ───────────────────────────────────────────────────

def call_analyze(image_url: str, api_key: str) -> dict:
    print("⚡ API'ye istek gönderiliyor...")
    start = time.time()

    response = requests.post(
        f"{API_BASE}/api/analyze",
        json={"id": str(uuid.uuid4()), "image_url": image_url},
        headers={"X-API-Key": api_key} if api_key else {},
        timeout=60,
    )

    elapsed = round(time.time() - start, 2)

    if response.status_code != 200:
        print(f"❌ Hata: HTTP {response.status_code}")
        print(response.text)
        exit(1)

    data = response.json()
    data["_elapsed"] = elapsed
    data["_image_url"] = image_url
    print(f"✅ Yanıt alındı: {elapsed}s")
    
    return data


# ── HTML Üretimi ──────────────────────────────────────────────────

def b64_to_img_tag(b64: str | None, alt: str = "") -> str:
    if not b64:
        return f'<div class="no-img">Görsel yok</div>'
    return f'<img src="data:image/jpeg;base64,{b64}" alt="{alt}" />'


def build_html(data: dict) -> str:
    is_fake       = data.get("IsDeepfake", False)
    confidence    = data.get("CnnConfidence", 0)
    ela_score     = data.get("ElaScore", 0) or 0
    fft_score     = data.get("FftAnomalyScore", 0) or 0
    elapsed       = data.get("_elapsed", 0)
    image_url     = data.get("_image_url", "")
    record_id     = data.get("Id", "")
    has_exif      = data.get("ExifHasMetadata", False)
    camera        = data.get("ExifCameraInfo") or "Bilinmiyor"
    indicators    = data.get("ExifSuspiciousIndicators") or ""
    indicators    = [i.strip() for i in indicators.split(";") if i.strip()]
    status        = data.get("Status", "Completed")
    now           = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    # --- DÜZELTME BURADA ---
    # API bazen "Image" bazen "ImageBase64" anahtarı döndürüyor olabilir.
    # İkisini de kontrol edip, varsa new line karakterlerini temizliyoruz.
    
    def get_img(key_root):
        # Önce "XImage" sonra "XImageBase64" anahtarına bakar
        val = data.get(f"{key_root}Image") or data.get(f"{key_root}ImageBase64")
        if val:
            return val.replace("\n", "") # Base64 içindeki satır sonlarını temizle
        return None

    gradcam_b64 = get_img("Gradcam")
    ela_b64     = get_img("Ela")
    fft_b64     = get_img("Fft")
   
    # -----------------------

    verdict_text  = "DEEPFAKE / YAPAY" if is_fake else "GERÇEK GÖRÜNTÜ"
    verdict_color = "#ff4757" if is_fake else "#2ed573"
    verdict_bg    = "rgba(255,71,87,0.12)" if is_fake else "rgba(46,213,115,0.12)"
    verdict_icon  = "⚠" if is_fake else "✓"

    indicators_html = "".join(
        f'<li class="flag-item">{i}</li>' for i in indicators
    ) if indicators else '<li class="flag-item ok">Anomali tespit edilmedi</li>'

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DeepFake Analiz Raporu</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:       #0a0a0f;
    --surface:  #12121a;
    --border:   #1e1e2e;
    --text:     #e0e0f0;
    --muted:    #666680;
    --accent:   #7c6af7;
    --fake:     #ff4757;
    --real:     #2ed573;
    --warn:     #ffa502;
  }}

  * {{ margin:0; padding:0; box-sizing:border-box; }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Syne', sans-serif;
    min-height: 100vh;
    padding: 32px 24px 64px;
  }}

  /* ── Header ── */
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    border-bottom: 1px solid var(--border);
    padding-bottom: 24px;
    margin-bottom: 32px;
  }}
  .header-title {{ font-size: 13px; color: var(--muted); letter-spacing: 0.15em; text-transform: uppercase; }}
  .header-id    {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--muted); margin-top: 6px; }}
  .header-time  {{ text-align: right; font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--muted); }}

  /* ── Verdict ── */
  .verdict {{
    background: {verdict_bg};
    border: 1px solid {verdict_color}44;
    border-radius: 12px;
    padding: 28px 32px;
    margin-bottom: 28px;
    display: flex;
    align-items: center;
    gap: 24px;
  }}
  .verdict-icon {{
    font-size: 52px;
    color: {verdict_color};
    line-height: 1;
  }}
  .verdict-label {{
    font-size: 11px;
    color: var(--muted);
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin-bottom: 6px;
  }}
  .verdict-text {{
    font-size: 32px;
    font-weight: 800;
    color: {verdict_color};
    letter-spacing: -0.02em;
  }}
  .verdict-conf {{
    margin-top: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    color: var(--muted);
  }}

  /* ── Stats Grid ── */
  .stats {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 28px;
  }}
  @media (max-width: 700px) {{ .stats {{ grid-template-columns: repeat(2, 1fr); }} }}

  .stat {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
  }}
  .stat-label {{
    font-size: 10px;
    color: var(--muted);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 8px;
  }}
  .stat-value {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 22px;
    font-weight: 700;
    color: var(--accent);
  }}
  .stat-bar {{
    height: 3px;
    background: var(--border);
    border-radius: 99px;
    margin-top: 10px;
    overflow: hidden;
  }}
  .stat-bar-fill {{
    height: 100%;
    border-radius: 99px;
    transition: width 1s ease;
  }}

  /* ── Görseller Grid ── */
  .images-title {{
    font-size: 11px;
    color: var(--muted);
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin-bottom: 16px;
  }}
  .images-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
    margin-bottom: 28px;
  }}
  @media (max-width: 600px) {{ .images-grid {{ grid-template-columns: 1fr; }} }}

  .img-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
    cursor: pointer;
    transition: border-color .2s, transform .2s;
  }}
  .img-card:hover {{
    border-color: var(--accent);
    transform: translateY(-2px);
  }}
  .img-card-label {{
    padding: 10px 14px;
    font-size: 10px;
    color: var(--muted);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .img-card-label span {{ color: var(--accent); font-family: 'JetBrains Mono', monospace; }}
  .img-card img {{
    width: 100%;
    display: block;
    max-height: 280px;
    object-fit: cover;
  }}
  .no-img {{
    padding: 40px;
    text-align: center;
    color: var(--muted);
    font-size: 12px;
  }}

  /* ── Metadata ── */
  .meta-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 28px;
  }}
  .meta-card-title {{
    font-size: 10px;
    color: var(--muted);
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin-bottom: 16px;
  }}
  .meta-row {{
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
  }}
  .meta-row:last-child {{ border-bottom: none; }}
  .meta-key   {{ color: var(--muted); font-family: 'JetBrains Mono', monospace; font-size: 11px; }}
  .meta-val   {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--text); }}
  .flag-list  {{ list-style: none; margin-top: 8px; }}
  .flag-item  {{
    padding: 6px 10px;
    margin: 4px 0;
    background: rgba(255,71,87,0.08);
    border-left: 3px solid var(--fake);
    border-radius: 4px;
    font-size: 12px;
    font-family: 'JetBrains Mono', monospace;
  }}
  .flag-item.ok {{
    background: rgba(46,213,115,0.08);
    border-left-color: var(--real);
  }}

  /* ── Lightbox ── */
  .lightbox {{
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,.92);
    z-index: 1000;
    justify-content: center;
    align-items: center;
    cursor: zoom-out;
  }}
  .lightbox.open {{ display: flex; }}
  .lightbox img  {{ max-width: 92vw; max-height: 92vh; border-radius: 8px; }}

  /* ── Footer ── */
  .footer {{
    text-align: center;
    font-size: 11px;
    color: var(--muted);
    margin-top: 48px;
    padding-top: 24px;
    border-top: 1px solid var(--border);
    font-family: 'JetBrains Mono', monospace;
  }}
</style>
</head>
<body>

<div class="lightbox" id="lightbox" onclick="closeLightbox()">
  <img id="lb-img" src="" alt="">
</div>

<div class="header">
  <div>
    <div class="header-title">DeepFake Detection · Analiz Raporu</div>
    <div class="header-id">ID: {record_id}</div>
  </div>
  <div class="header-time">
    <div>{now}</div>
    <div style="margin-top:4px">⏱ {elapsed}s</div>
  </div>
</div>

<div class="verdict">
  <div class="verdict-icon">{verdict_icon}</div>
  <div>
    <div class="verdict-label">Analiz Sonucu</div>
    <div class="verdict-text">{verdict_text}</div>
    <div class="verdict-conf">CNN Güveni: {confidence*100:.1f}% &nbsp;|&nbsp; Durum: {status}</div>
  </div>
</div>

<div class="stats">
  <div class="stat">
    <div class="stat-label">CNN Güveni</div>
    <div class="stat-value">{confidence*100:.1f}%</div>
    <div class="stat-bar"><div class="stat-bar-fill" style="width:{confidence*100:.1f}%;background:{'var(--fake)' if is_fake else 'var(--real)'}"></div></div>
  </div>
  <div class="stat">
    <div class="stat-label">ELA Skoru</div>
    <div class="stat-value">{ela_score*100:.1f}%</div>
    <div class="stat-bar"><div class="stat-bar-fill" style="width:{ela_score*100:.1f}%;background:var(--warn)"></div></div>
  </div>
  <div class="stat">
    <div class="stat-label">FFT Anomali</div>
    <div class="stat-value">{fft_score*100:.1f}%</div>
    <div class="stat-bar"><div class="stat-bar-fill" style="width:{fft_score*100:.1f}%;background:var(--accent)"></div></div>
  </div>
  <div class="stat">
    <div class="stat-label">İşlem Süresi</div>
    <div class="stat-value">{elapsed}s</div>
    <div class="stat-bar"><div class="stat-bar-fill" style="width:min(100%,{elapsed/30*100:.1f}%);background:var(--muted)"></div></div>
  </div>
</div>

<div class="images-title">Analiz Görselleri · tıklayarak büyütün</div>
<div class="images-grid">

  <div class="img-card" onclick="openLightbox(this.querySelector('img'))">
    <div class="img-card-label">Grad-CAM <span>model odak haritası</span></div>
    {b64_to_img_tag(gradcam_b64, "Grad-CAM")}
  </div>

  <div class="img-card" onclick="openLightbox(this.querySelector('img'))">
    <div class="img-card-label">ELA Heatmap <span>manipülasyon haritası</span></div>
    {b64_to_img_tag(ela_b64, "ELA")}
  </div>

  <div class="img-card" onclick="openLightbox(this.querySelector('img'))">
    <div class="img-card-label">FFT Spektrum <span>frekans analizi</span></div>
    {b64_to_img_tag(fft_b64, "FFT")}
  </div>

  <div class="img-card" onclick="openLightbox(this.querySelector('img'))">
    <div class="img-card-label">Thumbnail <span>orijinal küçük</span></div>
    <img src="{image_url}" />'
  </div>

</div>

<div class="meta-card">
  <div class="meta-card-title">Metadata / EXIF Analizi</div>
  <div class="meta-row">
    <span class="meta-key">has_metadata</span>
    <span class="meta-val" style="color:{'var(--real)' if has_exif else 'var(--fake)'}">
      {'✓ EVET' if has_exif else '✗ HAYIR'}
    </span>
  </div>
  <div class="meta-row">
    <span class="meta-key">camera_info</span>
    <span class="meta-val">{camera}</span>
  </div>
  <div class="meta-row" style="flex-direction:column;gap:8px">
    <span class="meta-key">suspicious_indicators</span>
    <ul class="flag-list">{indicators_html}</ul>
  </div>
</div>

<div class="meta-card">
  <div class="meta-card-title">Kaynak</div>
  <div class="meta-row">
    <span class="meta-key">image_url</span>
    <span class="meta-val" style="word-break:break-all;max-width:75%;text-align:right">{image_url[:80]}{'...' if len(image_url)>80 else ''}</span>
  </div>
  <div class="meta-row">
    <span class="meta-key">record_id</span>
    <span class="meta-val">{record_id}</span>
  </div>
</div>

<div class="footer">
  Deepfake Detection API · v3.0.0 · Bu sistem bir karar destek aracıdır,
  hukuki doğrulama aracı olarak kullanılamaz.
</div>

<script>
  function openLightbox(img) {{
    if (!img) return;
    document.getElementById('lb-img').src = img.src;
    document.getElementById('lightbox').classList.add('open');
  }}
  function closeLightbox() {{
    document.getElementById('lightbox').classList.remove('open');
  }}
  document.addEventListener('keydown', e => {{ if(e.key==='Escape') closeLightbox(); }});
</script>
</body>
</html>"""

# ── Main ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deepfake API Görsel Viewer")
    parser.add_argument("--url", default=DEFAULT_URL,  help="Görüntü URL'si")
    parser.add_argument("--key", default=DEFAULT_KEY,  help="API Key")
    parser.add_argument("--out", default=OUTPUT_FILE,  help="HTML çıktı dosyası")
    args = parser.parse_args()

    # Sağlık kontrolü
    try:
        h = requests.get(f"{API_BASE}/health", timeout=5).json()
        key_st = "🔓 KAPALI" if not h.get("api_key_enabled") else "🔒 AKTİF"
        print(f"✅ API çalışıyor  |  API Key: {key_st}\n")
    except Exception:
        print("❌ API çalışmıyor!\n   uvicorn app.main:app --reload --port 8000")
        exit(1)

    # API çağrısı
    data = call_analyze(args.url, args.key)

    # HTML üret
    html = build_html(data)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)

    abs_path = os.path.abspath(args.out)
    print(f"📄 HTML rapor: {abs_path}")

    # Browser'da aç
    print("🌐 Browser'da açılıyor...")
    webbrowser.open(f"file://{abs_path}")