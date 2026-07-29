# Backend Update Notes

File ini hanya berisi update kode. Environment seperti `.env`, `.venv`, dan `chroma_db/` tidak diubah.

Yang di-update:

1. Fix import path admin upload dari `config/ingest` menjadi `uploads.config/uploads.ingest`.
2. `requirements.txt` diperbaiki dari format command menjadi daftar dependency valid.
3. Upload endpoint sekarang return `totalChunks`, `pages`, `collection`, dan `embeddingModel`.
4. Ingestion sekarang return hasil indexing, bukan `None`.
5. ChromaDB memakai `upsert`, bukan `add`, supaya re-upload tidak gampang error duplicate ID.
6. Ditambahkan hybrid retrieval: semantic vector search + BM25/keyword fallback.
7. Ditambahkan endpoint `POST /query` untuk ambil chunks relevan.
8. Ditambahkan endpoint `POST /chat` untuk jawaban extractive + citation.
9. Query logs sudah real lewat `api/logger.py` dan bisa dibaca dari `GET /admin/logs`.
10. `.gitignore` diperbaiki supaya kode di `uploads/*.py` tidak ikut ke-ignore.

Cara jalan:

```bash
cd backend
pip install -r requirements.txt
uvicorn api.main:app --reload
```

Test endpoint:

```bash
curl http://127.0.0.1:8000/health
```

Upload dokumen:

```bash
curl -X POST "http://127.0.0.1:8000/admin/upload" -F "file=@SOP_Onboarding.pdf"
```

Query retrieval:

```bash
curl -X POST "http://127.0.0.1:8000/query" -H "Content-Type: application/json" -d '{"query":"How long is the probation period?","top_k":5}'
```

Chat:

```bash
curl -X POST "http://127.0.0.1:8000/chat" -H "Content-Type: application/json" -d '{"question":"How long is the probation period?","top_k":5}'
```
