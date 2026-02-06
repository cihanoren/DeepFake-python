import time
import requests
from pathlib import Path

API_URL = "http://localhost:8000/api/analyze"
TEST_IMAGE = "test-image/manzara.jpeg"
NUM_REQUESTS = 5

def benchmark():
    times = []
    
    print(f"🧪 {NUM_REQUESTS} istek gönderiliyor...\n")
    
    for i in range(NUM_REQUESTS):
        start = time.time()
        
        with open(TEST_IMAGE, 'rb') as f:
            files = {'file': f}
            response = requests.post(API_URL, files=files, timeout=60)
        
        elapsed = time.time() - start
        times.append(elapsed)
        
        print(f"İstek {i+1}: {elapsed:.2f}s - {response.status_code}")
    
    print(f"\n📊 Sonuçlar:")
    print(f"   Ortalama: {sum(times)/len(times):.2f}s")
    print(f"   En Hızlı: {min(times):.2f}s")
    print(f"   En Yavaş: {max(times):.2f}s")

if __name__ == "__main__":
    benchmark()