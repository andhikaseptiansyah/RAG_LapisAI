from __future__ import annotations

import api.ollama_client as ollama
from api.answer_formatter import is_refusal_answer


def chunk(content: str) -> dict:
    return {
        "chunkId": "c1",
        "documentName": "Policy_Remote_Work.docx",
        "page": 1,
        "content": content,
        "score": 0.92,
        "baseScore": 0.88,
        "semanticScore": 0.90,
        "keywordScore": 0.80,
        "exactTokenCoverage": 0.50,
        "evidenceScore": 0.90,
        "evidenceSupported": True,
        "evidenceHardFailures": [],
        "answerabilityAccepted": True,
        "answerabilityScore": 0.88,
        "metadata": {"filename": "Policy_Remote_Work.docx", "page": 1},
    }


def test_model_refusal_returns_control_to_chat_service(monkeypatch) -> None:
    monkeypatch.setattr(
        ollama,
        "_ollama_chat",
        lambda *args, **kwargs: (
            "The requested information was not found with sufficient evidence in the indexed documents.",
            "stop",
        ),
    )
    answer = ollama.build_ollama_grounded_answer(
        "What is the maximum reimbursement?",
        [chunk("The maximum reimbursement is IDR 1,500,000.")],
        language="EN",
    )
    assert answer == ""


def test_hallucinated_amount_is_repaired(monkeypatch) -> None:
    responses = iter(
        [
            ("The maximum reimbursement is IDR 2,000,000.", "stop"),
            ("The maximum reimbursement is IDR 1,500,000.", "stop"),
        ]
    )
    monkeypatch.setattr(ollama, "_ollama_chat", lambda *args, **kwargs: next(responses))
    answer = ollama.build_ollama_grounded_answer(
        "What is the maximum reimbursement?",
        [chunk("The maximum reimbursement is IDR 1,500,000.")],
        language="EN",
    )
    assert "1,500,000" in answer
    assert "2,000,000" not in answer
