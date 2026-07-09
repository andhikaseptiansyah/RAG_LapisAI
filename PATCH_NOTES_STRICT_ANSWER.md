# Strict Grounded Answer Patch

Perbaikan utama:

1. `api/answer_formatter.py` dibuat lebih ketat.
   - Tidak lagi membuang seluruh isi chunk ke jawaban.
   - Pertanyaan definisi seperti "apa itu JITEK" diproses dengan mode definisi.
   - Jawaban dibatasi pendek: bagian Jawaban, Sumber, Confidence.
   - Noise seperti daftar pustaka, gambar, tabel, ISSN, dan boilerplate paper dikurangi.

2. `api/routes_compat.py` harus sudah meng-import formatter ini.
   - Kalau jawaban masih diawali "Berdasarkan dokumen yang paling relevan...", berarti file `api/routes_compat.py` lama masih aktif atau backend belum di-restart.

Cara pakai:

```powershell
cd C:\Users\ANDIKA\Downloads\RAG_LapisAI\backend
python -m uvicorn api.main:app --host 127.0.0.1 --port 5000 --log-level debug
```

Test:

```powershell
$chatBody = @{ message = "apa itu JITEK"; language = "ID" } | ConvertTo-Json -Compress
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/chat" -Method POST -ContentType "application/json" -Headers @{ Authorization = "Bearer $token" } -Body $chatBody
```

Target jawaban:

```text
Jawaban:
JITEK adalah singkatan/nama dari Jurnal Ilmiah Teknik Informatika dan Elektro (JITEK).

Sumber:
- 5669-19166-1-PB.pdf, p. 5

Confidence: xx%
```
