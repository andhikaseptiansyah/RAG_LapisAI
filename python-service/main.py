from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from rag_pipeline import store


class IndexRequest(BaseModel):
    document_id: str = Field(..., alias="documentId")
    file_path: str = Field(..., alias="filePath")
    filename: str
    metadata: Optional[Dict[str, Any]] = None


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, alias="topK")
    min_score: float = Field(default=0.0, alias="minScore")


app = FastAPI(title="LapisAI Python RAG Service", version="1.0.0")


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "lapisai-python-rag",
    }


@app.post("/index")
def index_document(payload: IndexRequest) -> Dict[str, Any]:
    try:
        result = store.index_document(
            document_id=payload.document_id,
            file_path=payload.file_path,
            filename=payload.filename,
            extra_metadata=payload.metadata,
        )
        return {
            "status": "indexed",
            **result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/retrieve")
def retrieve(payload: RetrieveRequest) -> Dict[str, Any]:
    try:
        chunks = store.retrieve(
            query=payload.query,
            top_k=payload.top_k,
            min_score=payload.min_score,
        )
        return {"chunks": chunks}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
