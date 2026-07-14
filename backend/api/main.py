from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes_admin import router as admin_router
from api.routes_chat import router as chat_router
from api.routes_compat import router as compat_router
from retrieval.hybrid_search import warmup_retrieval


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm up retrieval models before the first user request."""

    status = warmup_retrieval()

    print(
        "[RETRIEVAL] warm-up "
        f"embedding={'ready' if status['embedding'] else 'fallback'}; "
        f"reranker={'ready' if status['reranker'] else 'fallback/disabled'}"
    )

    yield


app = FastAPI(
    title="Enterprise Knowledge Assistant API",
    version="1.0.0",
    lifespan=lifespan,
)


# CORS configuration
# Mengizinkan frontend lokal dan frontend production
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


# Admin API
app.include_router(
    admin_router,
    prefix="/admin",
    tags=["admin"],
)


# Main chat API
app.include_router(
    chat_router,
    tags=["chat"],
)


# Frontend compatibility API
app.include_router(
    compat_router,
    prefix="/api",
    tags=["frontend-compat"],
)


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Enterprise Knowledge Assistant API is running",
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
    }