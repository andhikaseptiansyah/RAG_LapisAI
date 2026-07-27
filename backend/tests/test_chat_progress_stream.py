from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.routes_compat as routes
from api.progress import emit_progress, progress_scope


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    parsed: list[tuple[str, dict]] = []
    for block in body.strip().split("\n\n"):
        event_name = "message"
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].lstrip())
        if data_lines:
            parsed.append((event_name, json.loads("\n".join(data_lines))))
    return parsed


def test_progress_scope_emits_only_operational_payload() -> None:
    events: list[dict] = []
    with progress_scope(events.append):
        emit_progress(
            "reranking",
            "active",
            "Melakukan reranking",
            detail="Memeriksa 20 kandidat dokumen.",
            metadata={"candidateCount": 20},
        )

    assert events == [
        {
            "step": "reranking",
            "status": "active",
            "title": "Melakukan reranking",
            "timestamp": events[0]["timestamp"],
            "detail": "Memeriksa 20 kandidat dokumen.",
            "metadata": {"candidateCount": 20},
        }
    ]
    serialized = json.dumps(events, ensure_ascii=False).casefold()
    assert "chain-of-thought" not in serialized
    assert "system prompt" not in serialized
    assert "chunking dokumen" not in serialized
    assert "embedding dokumen" not in serialized


def test_chat_stream_sends_progress_then_result(monkeypatch) -> None:
    monkeypatch.setattr(
        routes,
        "_require_user",
        lambda request: {"id": "user-1", "name": "Tester", "role": "user"},
    )
    monkeypatch.setattr(routes, "save_log", lambda **kwargs: kwargs)
    monkeypatch.setattr(
        routes,
        "append_chat_turn",
        lambda **kwargs: (
            {"id": "conversation-1"},
            {"id": "message-1", "created_at": "2026-07-27T00:00:00Z"},
        ),
    )

    def fake_run_chat(question: str, **kwargs):
        progress_callback = kwargs["progress_callback"]
        progress_callback(
            {
                "step": "analyze",
                "status": "completed",
                "title": "Pertanyaan berhasil dianalisis",
            }
        )
        progress_callback(
            {
                "step": "reranking",
                "status": "active",
                "title": "Melakukan reranking",
                "detail": "Memeriksa 12 kandidat dokumen.",
            }
        )
        return {
            "answer": "Jawaban uji.",
            "confidence": 0.91,
            "sources": [
                {
                    "document_name": "SOP_IT_Incident_Handling.pdf",
                    "page": 1,
                    "paragraph_start": 2,
                    "score": 0.91,
                }
            ],
            "follow_up_question": None,
            "response_time_ms": 10,
            "language": "ID",
            "model": "gemini-rag",
            "generation_mode": "native_model",
            "buildVersion": "test-build",
            "retrieval_mode": "original",
            "retrieval_query": question,
            "failure_stage": None,
        }

    monkeypatch.setattr(routes, "run_chat", fake_run_chat)

    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    client = TestClient(app)

    with client.stream(
        "POST",
        "/api/chat/stream",
        json={"message": "Berapa target P1?", "queryId": "query-1"},
    ) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(body)
    names = [name for name, _ in events]
    assert names[0] == "ready"
    assert names.count("progress") == 2
    assert names[-1] == "result"

    result = events[-1][1]
    assert result["answer"] == "Jawaban uji."
    assert result["source"] == "SOP_IT_Incident_Handling.pdf"
    assert result["page"] == 1


def test_admin_evaluation_chat_uses_native_mode_without_persistence(monkeypatch) -> None:
    monkeypatch.setattr(
        routes,
        "_require_admin",
        lambda request: {"id": "admin-1", "name": "Admin", "role": "admin"},
    )
    calls: list[dict] = []

    def fake_run_chat(question: str, **kwargs):
        calls.append({"question": question, **kwargs})
        return {
            "answer": "Jawaban benchmark.",
            "confidence": 0.9,
            "sources": [],
            "generation_contexts": [],
            "response_time_ms": 12,
            "model": "groq-rag",
            "generation_mode": "native_model",
            "language": "ID",
        }

    monkeypatch.setattr(routes, "run_chat", fake_run_chat)
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    client = TestClient(app)

    response = client.post(
        "/api/admin/evaluation/chat",
        json={
            "question": "Berapa target P1?",
            "language": "ID",
            "model": "groq",
            "topK": 7,
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "Jawaban benchmark."
    assert calls == [
        {
            "question": "Berapa target P1?",
            "top_k": 7,
            "language": "ID",
            "model": "groq",
            "evaluation_mode": True,
        }
    ]
