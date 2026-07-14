import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.chat_service import run_chat
from api.logger import save_log
from retrieval.hybrid_search import hybrid_search

router = APIRouter()


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    language: str = Field(default="ID")


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class ChatSourceResponse(BaseModel):
    document_name: str
    page: int | str | None = None
    score: float = Field(ge=0.0, le=1.0)
    excerpt: str = ""
    section: str | None = None
    paragraph_start: int | None = None
    paragraph_end: int | None = None
    line_start: int | None = None
    line_end: int | None = None


class ChatResponse(BaseModel):
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[ChatSourceResponse]
    follow_up_question: str | None = None
    response_time_ms: int = Field(ge=0)


@router.post("/query")
def query_documents(payload: QueryRequest):
    started_at = time.perf_counter()

    try:
        chunks = hybrid_search(payload.query, top_k=payload.top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(exc)}") from exc

    latency_ms = (time.perf_counter() - started_at) * 1000

    return {
        "query": payload.query,
        "chunks": chunks,
        "retrieval": {
            "mode": "hybrid",
            "topK": payload.top_k,
            "latencyMs": round(latency_ms, 2),
        },
    }


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> dict[str, Any]:
    try:
        result = run_chat(
            payload.question,
            top_k=payload.top_k,
            language=payload.language,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(exc)}") from exc

    save_log(
        question=payload.question,
        answer=result["answer"],
        sources=result["sources"],
        latency_ms=result["response_time_ms"],
        confidence=result["confidence"],
    )

    return {
        "answer": result["answer"],
        "confidence": result["confidence"],
        "sources": result["sources"],
        "follow_up_question": result.get("follow_up_question"),
        "response_time_ms": result["response_time_ms"],
    }
