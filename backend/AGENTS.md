# AGENTS.md

## Project layout

| Directory | Purpose |
|-----------|---------|
| `api/` | FastAPI app (`main.py` entrypoint, `routes_admin.py`) |
| `ingestion/` | Pipeline: `parser.py` → `chunker.py` → `indexer.py` |
| `uploads/` | Shared config, ingestion orchestrator (`ingest.py`) |

## Running

```powershell
# Start dev server (run from repo root)
uvicorn api.main:app --reload
```

## Import quirk

There are **no `__init__.py` files**. Python treats every directory as a namespace package.

`uploads/config.py` and `uploads/ingest.py` are imported **as bare module names** (`from config import UPLOAD_DIR`, `from ingest import ingest`) because the repo root is the working directory. Do not reorganise these imports — they only work from the repo root.

## Actual dependencies

`requirements.txt` is incomplete (only lists `python-docx pymupdf`). The full set already installed in `.venv`:

- `fastapi`, `uvicorn[standard]` — web server
- `sentence-transformers`, `chromadb` — embedding + vector store
- `python-docx`, `pymupdf` — file parsing

To regenerate requirements:
```powershell
.venv\Scripts\pip freeze > requirements.txt
```

## Config (single source)

All shared constants live in `uploads/config.py`:

```python
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # sentence-transformers model
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "knowledge_base"
UPLOAD_DIR = "./uploads"
```

Both `api/routes_admin.py` and `ingestion/indexer.py` reference these values — keep them in sync.

## Ingestion pipeline

```
Upload file → save to uploads/ → ingest(filepath)
  → parse_file (PDF/DOCX/TXT → pages)
  → chunk_pages (sliding window, ~750 token chunks with 100 token overlap)
  → embed_chunks (all-MiniLM-L6-v2)
  → index_chunks (ChromaDB persistent client)
```

Run standalone: `python uploads/ingest.py <filepath>`

## Known placeholders

- `api/routes_admin.py:35` — `GET /admin/logs` returns `{"logs": []}`
- `api/main.py:12` — CORS origin `https://rag-lapis-ai.vercel.app/` needs real URL
