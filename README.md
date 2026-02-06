# DeepFake-python

DeepFake / Yapay görsel tespiti için FastAPI tabanlı analiz servisi.  
(Proje: Bitirme Projesi)

---

## 🚀 Çalıştırma

### 1️⃣ Projeyi klonla
```bash
git clone https://github.com/cihanoren/DeepFake-python.git
cd DeepFake-python


⸻

2️⃣ Sanal ortam oluştur ve aktif et

macOS / Linux

python3 -m venv venv
source venv/bin/activate

Windows

python -m venv venv
venv\Scripts\activate


⸻

3️⃣ Bağımlılıkları yükle

pip install --upgrade pip
pip install -r requirements.txt


⸻

▶️ Sunucuyu Çalıştırma

🔧 Development Modu

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

🚀 Production Modu

uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4


⸻

🧪 Test

📘 Swagger UI

Tarayıcıdan:

http://localhost:8000/docs


⸻

🔗 cURL ile API Testi

curl -X POST "http://localhost:8000/api/analyze" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test-image/manzara.jpeg"



⸻

📂 Proje Yapısı

DeepFake-python/
│
├── app/
│   ├── main.py
│   ├── routes/
│   └── services/
│
├── test-image/
│   └── sample.jpg
│
├── requirements.txt
├── benchmark.py
└── README.md


⸻

🧠 Notlar
	•	API FastAPI + Uvicorn ile çalışır
	•	Görsel analizinde ELA ve/veya CNN tabanlı yöntemler kullanılmaktadır
	•	Python 3.10 / 3.11 önerilir

---
