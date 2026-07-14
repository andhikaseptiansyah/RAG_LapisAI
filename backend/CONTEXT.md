# Project Context: Enterprise Knowledge Assistant (RAG Platform)

## What This Project Is
A RAG (Retrieval-Augmented Generation) pipeline that lets enterprise users query internal documents (PDF, DOCX, TXT) using natural language. Answers come with source citations (filename + page number).

---

## Current Progress (Ingestion Pipeline + API Layer)

### Folder Structure
```
backend/
├── ingestion/
│   ├── __init__.py
│   ├── parser.py       # Extracts text + page metadata from PDF, DOCX, TXT
│   ├── chunker.py      # Splits text into overlapping chunks
│   └── indexer.py      # Embeds chunks + stores in ChromaDB
├── retrieval/          # NOT YET BUILT (Member B's responsibility)
│   └── __init__.py
├── api/
│   ├── __init__.py
│   ├── main.py         # FastAPI app + CORS config
│   └── routes_admin.py # POST /admin/upload, GET /admin/logs
├── uploads/            # Temp storage for uploaded files
├── chroma_db/          # Auto-generated, do NOT commit to git
├── config.py           # Shared constants
└── ingest.py           # Entry point: parse → chunk → index
```

---

## Key Design Decisions

| Decision | Value | Reason |
|---|---|---|
| Chunk size | 750 tokens (target) | PRD spec: 500-1000 tokens |
| Overlap | 100 tokens | PRD spec, prevents boundary loss |
| Chunking strategy | Sliding window | Predictable, matches PRD spec |
| Token counting | Word count x 1.3 approximation | Lightweight, no extra dependency |
| Embedding model | `all-MiniLM-L6-v2` | Free, fast, 384-dim |
| Vector store | ChromaDB (persistent) | Local, survives restarts |
| DOCX page numbers | Approximated per 10 paragraphs | python-docx limitation |
| TXT page numbers | Approximated per 50 lines | No native page concept |

---

## How Each File Works

### `ingestion/parser.py`
- `parse_file(filepath)` — main entry point, routes by file extension
- `parse_pdf()` — uses PyMuPDF (`fitz`), real page numbers
- `parse_docx()` — uses python-docx, logical pages (10 paragraphs = 1 page)
- `parse_txt()` — plain read, logical pages (50 lines = 1 page)
- Output: `[{text, page, filename}, ...]`

### `ingestion/chunker.py`
- `chunk_text(text)` — sliding window, converts token targets to word counts, fixed step to prevent infinite loops
- `chunk_pages(pages)` — applies chunking to all pages, assigns `chunk_id`
- Output: `[{chunk_id, text, page, filename}, ...]`
- `chunk_id` format: `filename_pPAGE_cINDEX` e.g. `SOP.pdf_p1_c0`

### `ingestion/indexer.py`
- Loads `SentenceTransformer` once at module level
- `embed_chunks(chunks)` — batch encodes all chunk texts, attaches embeddings
- `index_chunks(chunks)` — stores into ChromaDB with metadata `{filename, page}`
- Uses `get_or_create_collection` to be safe on restarts

### `ingest.py`
- Single entry point: `ingest(filepath)`
- Calls parse → chunk → index in sequence
- Can also be run via CLI: `python ingest.py <filepath>`

### `config.py`
```python
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "knowledge_base"
UPLOAD_DIR = "./uploads"
```
**Member B must import from this file — especially `EMBEDDING_MODEL` and `COLLECTION_NAME`.**

### `api/main.py`
- FastAPI app with CORS middleware
- Replace `https://your-frontend.vercel.app` with real Vercel URL
- Includes admin router under `/admin` prefix
- `GET /health` — sanity check endpoint

### `api/routes_admin.py`
- `POST /admin/upload` — receives file, validates extension, saves to `uploads/`, calls `ingest()`
- `GET /admin/logs` — stub, returns empty list until query logging is built

---

## What's Left to Build

### Member B — Retrieval (`backend/retrieval/`)
- `hybrid_search.py` — BM25 (lexical) + dense vector search, fused via RRF
- `reranker.py` — cross-encoder reranking, top-20 → top-5
- `POST /chat` endpoint — takes question, returns answer + citations + confidence score
- Must use same `EMBEDDING_MODEL` and `COLLECTION_NAME` from `config.py`

### Member C — Query Logging
- Log each query: question, answer, source docs, latency, timestamp
- Wire into `GET /admin/logs`

### Member D — Evaluation
- RAGAS evaluation suite against ~50 ground-truth Q&A pairs
- Metrics: Faithfulness, Context Precision, Context Recall, Answer Relevance

### Everyone — Demo + Business Case
- Live demo: Windows Explorer search vs RAG assistant
- Edge case demo: question outside document scope
- RAGAS metrics slide
- B2B SaaS pricing deck

---

## How to Run Locally
```bash
cd backend
pip install -r requirements.txt
uvicorn api.main:app --reload
```

## Important: Do NOT Commit
- `chroma_db/` — local vector database, auto-generated
- `uploads/` — temp files
- `.env` — API keys
- `__pycache__/`
