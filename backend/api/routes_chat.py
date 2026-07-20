import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.answer_formatter import build_evidence_excerpt
from api.chat_service import run_chat
from api.logger import save_log
from retrieval.context_selector import select_context_bundle
from retrieval.hybrid_search import hybrid_search
from uploads.config import (
    CONTEXT_REDUNDANCY_THRESHOLD,
    CONTEXT_SECONDARY_SCORE_RATIO,
    MAX_GENERATION_CONTEXTS,
)

router = APIRouter()


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    language: str = Field(default="ID")
    query_id: str | None = None


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    generation_context: bool = Field(default=False)


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


class GenerationContextResponse(BaseModel):
    text: str
    document_name: str = ""
    page: int | str | None = None
    chunk_id: str = ""


class ChatResponse(BaseModel):
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[ChatSourceResponse]
    generation_contexts: list[GenerationContextResponse] = Field(default_factory=list)
    follow_up_question: str | None = None
    response_time_ms: int = Field(ge=0)


@router.post("/query")
def query_documents(payload: QueryRequest):
    started_at = time.perf_counter()

    try:
        chunks = hybrid_search(payload.query, top_k=payload.top_k)
        raw_candidate_count = len(chunks)
        if payload.generation_context:
            chunks = select_context_bundle(
                payload.query,
                chunks,
                max_contexts=MAX_GENERATION_CONTEXTS,
                redundancy_threshold=CONTEXT_REDUNDANCY_THRESHOLD,
                secondary_score_ratio=CONTEXT_SECONDARY_SCORE_RATIO,
            )
            chunks = [
                {
                    **chunk,
                    "content": build_evidence_excerpt(
                        payload.query,
                        str(chunk.get("content") or ""),
                    ) or str(chunk.get("content") or ""),
                    "generationContext": True,
                }
                for chunk in chunks
            ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(exc)}") from exc

    latency_ms = (time.perf_counter() - started_at) * 1000

    return {
        "query": payload.query,
        "chunks": chunks,
        "retrieval": {
            "mode": "hybrid",
            "topK": payload.top_k,
            "returnedContexts": len(chunks),
            "rawCandidateCount": raw_candidate_count,
            "generationContext": payload.generation_context,
            "latencyMs": round(latency_ms, 2),
        },
    }


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> dict[str, Any]:
    started_at = time.perf_counter()

    try:
        result = run_chat(
            payload.question,
            top_k=payload.top_k,
            language=payload.language,
        )
    except Exception as exc:
        save_log(
            query_id=payload.query_id,
            question=payload.question,
            answer="",
            sources=[],
            latency_ms=(time.perf_counter() - started_at) * 1000,
            confidence=0.0,
            status="NOT_FOUND",
            failure_reason="SERVER_ERROR",
        )
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(exc)}") from exc

    save_log(
        query_id=payload.query_id,
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
        "generation_contexts": result.get("generation_contexts", []),
        "follow_up_question": result.get("follow_up_question"),
        "response_time_ms": result["response_time_ms"],
    }
