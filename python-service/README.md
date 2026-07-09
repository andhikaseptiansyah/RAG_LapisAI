# LapisAI Python RAG Service

Service ini dibuat supaya Project 1 sesuai requirement: pipeline RAG utama memakai Python untuk document ingestion, chunking, embeddings, vector store, hybrid retrieval, dan citation source.

## Setup

```bash
cd python-service
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
python main.py
```

Default jalan di `http://localhost:8001`.

## Endpoint penting

- `GET /health`
- `POST /index` untuk parse PDF/DOCX/TXT, chunking, embedding, simpan ke ChromaDB
- `POST /retrieve` untuk semantic + BM25 retrieval

Backend Node memanggil service ini lewat env:

```env
RAG_PYTHON_URL=http://localhost:8001
```
