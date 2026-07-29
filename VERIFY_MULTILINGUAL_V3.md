# Verifikasi Multilingual V3

Build yang harus aktif:

```text
rag-multilingual-v3-20260723
```

Perbaikan ini tidak menurunkan threshold. Perubahan utama ialah menjalankan query asli dan query jembatan Inggris sebagai pencarian terpisah, mempertahankan token kode pendek seperti `P1`, lalu mengambil kandidat terbaik dari semantic search, BM25, dan reranker.

## 1. Pastikan backend yang benar aktif

Jalankan dari folder proyek:

```bash
python tools/verify_multilingual_v3.py --api-url http://127.0.0.1:8000
```

Atau periksa langsung:

```bash
curl http://127.0.0.1:8000/api/health
```

Respons wajib memuat:

```json
{
  "status": "ok",
  "buildVersion": "rag-multilingual-v3-20260723"
}
```

Jika `buildVersion` tidak ada atau nilainya berbeda, aplikasi masih terhubung ke backend lama. Restart proses Uvicorn, container, service, atau deployment backend. Build frontend saja tidak cukup.

Saat backend mulai, terminal juga harus menampilkan:

```text
[BUILD] active_backend=rag-multilingual-v3-20260723
```

## 2. Periksa alamat backend frontend

Frontend membaca alamat backend dari `VITE_API_URL`. Pastikan nilainya menunjuk ke server yang baru diperbarui. Nilai bawaan adalah:

```env
VITE_API_URL=http://127.0.0.1:8000
```

Perubahan `VITE_API_URL` memerlukan rebuild atau restart Vite.

## 3. Jalankan diagnosis retrieval

Endpoint ini memerlukan token administrator:

```bash
curl -X POST http://127.0.0.1:8000/api/admin/retrieval-debug \
  -H "Authorization: Bearer <TOKEN_ADMIN>" \
  -H "Content-Type: application/json" \
  -d '{"question":"Seberapa cepat insiden IT P1 harus diselesaikan?","topK":5}'
```

Alternatif:

```bash
python tools/verify_multilingual_v3.py \
  --api-url http://127.0.0.1:8000 \
  --token '<TOKEN_ADMIN>'
```

Periksa bagian berikut:

- `queryVariants` harus memuat pertanyaan asli dan query jembatan Inggris.
- Query jembatan harus memuat `P1 IT incident` dan `resolution time`.
- `finalCandidates` harus memuat bagian P1 dari `SOP_IT_Incident_Handling.pdf`.
- Kandidat P2 tidak boleh diterima sebagai jawaban P1.

## 4. Restart lokal

Contoh PowerShell:

```powershell
cd backend
$env:PYTHONPATH = "."
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

Contoh Bash:

```bash
cd backend
PYTHONPATH=. python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

Reindex tidak diperlukan untuk perubahan kode retrieval ini karena model embedding dan struktur collection tidak berubah. Reindex hanya diperlukan bila collection aktif tidak lagi berisi dokumen SOP tersebut atau dibuat menggunakan model embedding yang berbeda.
