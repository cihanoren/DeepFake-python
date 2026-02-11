"""
Benchmark – URL tabanlı API performans testi

Kullanım:
    python benchmark.py
    python3 benchmark.py --url https://example.com/photo.jpg --n 5 --key your-api-key
"""

import time
import argparse
import requests

API_BASE = "http://localhost:8000"

DEFAULT_IMAGE_URL = (
   "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEgI8hbyGkUDAF7hItsu4gTbLgrcM7YJLvTEL494jT4TR_fK3YKb9FRiWd0ZZOWUFFB20ZsAkGAYDvcxR5d9WC7WTy29BnOCobwqhNlfSaDjam8POajCwHVRIJaC9pitYr9Zu1x4h30uWEbE/s1600/The_Last_Supper_Jacopo_Bassano_1542.jpg"
)

# Varsayılan test key (.env ile eşleşmeli)
DEFAULT_API_KEY = "dev-secret-key-change-me"


def make_headers(api_key: str) -> dict:
    return {"X-API-Key": api_key} if api_key else {}


def test_endpoint(endpoint: str, image_url: str, record_id: str, api_key: str) -> dict:
    start    = time.time()
    response = requests.post(
        f"{API_BASE}{endpoint}",
        json={"id": record_id, "image_url": image_url},
        headers=make_headers(api_key),
        timeout=60,
    )
    elapsed = time.time() - start
    return {
        "endpoint": endpoint,
        "status":   response.status_code,
        "time":     round(elapsed, 2),
        "ok":       response.status_code == 200,
    }


def benchmark_routes(image_url: str, api_key: str):
    """Her route'u bir kez test et"""
    import uuid
    endpoints = ["/api/model", "/api/ela", "/api/fft", "/api/metadata", "/api/analyze"]

    print(f"\n{'='*55}")
    print("  ROUTE BAZLI BENCHMARK (tek istek)")
    print(f"{'='*55}\n")

    for ep in endpoints:
        r = test_endpoint(ep, image_url, str(uuid.uuid4()), api_key)
        status = "✅" if r["ok"] else f"❌ HTTP {r['status']}"
        print(f"  {ep:<22}  {r['time']:.2f}s  {status}")

    print()


def benchmark_full(image_url: str, n: int, api_key: str):
    """Ana endpoint'i n kez test et"""
    import uuid
    print(f"\n{'='*55}")
    print(f"  /api/analyze  –  {n} istek")
    print(f"{'='*55}\n")

    times = []
    for i in range(n):
        r = test_endpoint("/api/analyze", image_url, str(uuid.uuid4()), api_key)
        times.append(r["time"])
        icon = "✅" if r["ok"] else "❌"
        print(f"  İstek {i+1}: {r['time']:.2f}s  {icon}  HTTP {r['status']}")

    print(f"\n{'─'*55}")
    print(f"  Ortalama : {sum(times)/len(times):.2f}s")
    print(f"  En Hızlı : {min(times):.2f}s")
    print(f"  En Yavaş : {max(times):.2f}s")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deepfake API Benchmark")
    parser.add_argument("--url", default=DEFAULT_IMAGE_URL, help="Test görüntü URL'si")
    parser.add_argument("--n",   type=int, default=5,        help="Tekrar sayısı")
    parser.add_argument("--key", default=DEFAULT_API_KEY,    help="API Key (boş bırakılırsa header gönderilmez)")
    args = parser.parse_args()

    # Sağlık kontrolü
    try:
        health = requests.get(f"{API_BASE}/health", timeout=5)
        data   = health.json()
        key_status = "🔓 KAPALI" if not data.get("api_key_enabled") else "🔒 AKTİF"
        print(f"\n✅ API çalışıyor  |  API Key: {key_status}")
    except Exception:
        print("❌ API çalışmıyor! Önce sunucuyu başlatın:")
        print("   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        exit(1)

    benchmark_routes(args.url, args.key)
    benchmark_full(args.url, args.n, args.key)