from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api import ollama_client


def _chunk(content: str) -> dict:
    return {
        "chunkId": "allowance-1",
        "documentName": "Policy_Remote_Work.docx",
        "content": content,
        "score": 0.88,
        "baseScore": 0.76,
        "semanticScore": 0.74,
        "keywordScore": 0.62,
        "evidenceScore": 0.90,
        "evidenceSupported": True,
        "evidenceHardFailures": [],
        "answerabilityAccepted": True,
        "answerabilityScore": 0.86,
        "answerabilityEvidenceSelected": True,
        "metadata": {"filename": "Policy_Remote_Work.docx"},
    }


def test_hallucinated_llm_amount_is_never_returned(monkeypatch) -> None:
    monkeypatch.setattr(
        ollama_client,
        "_ollama_chat",
        lambda *args, **kwargs: ("Tunjangan home-office adalah IDR 2,000,000.", "stop"),
    )
    monkeypatch.setattr(ollama_client, "OLLAMA_MAX_RETRIES", 0)

    answer = ollama_client.build_ollama_grounded_answer(
        "Berapa tunjangan home-office?",
        [_chunk("Employees receive a one-time home-office allowance of IDR 1,500,000.")],
        language="ID",
    )

    assert "2,000,000" not in answer
    assert "2.000.000" not in answer
    assert answer == ""
