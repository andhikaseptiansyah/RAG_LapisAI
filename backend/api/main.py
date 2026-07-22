from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes_compat import router as api_router
from api.storage_paths import migrate_legacy_storage
from retrieval.hybrid_search import warmup_retrieval


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Migrate legacy stores and warm up retrieval models before requests."""
    migrated = migrate_legacy_storage()
    if migrated:
        print(f"[STORAGE] migrated legacy records: {migrated}")

    status = warmup_retrieval()
    print(
        "[RETRIEVAL] warm-up "
        f"embedding={'ready' if status['embedding'] else 'fallback'}; "
        f"reranker={'ready' if status['reranker'] else 'fallback/disabled'}"
    )
    yield


app = FastAPI(
    title="Enterprise Knowledge Assistant API",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "https://rag-lapis-ai.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Satu-satunya kontrak HTTP aktif. Router lama /chat, /query, /admin/upload,
# dan /admin/logs tidak lagi didaftarkan sehingga tidak dapat melewati autentikasi.
app.include_router(api_router, prefix="/api", tags=["api"])


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Enterprise Knowledge Assistant API is running",
        "apiBase": "/api",
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}
