from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.answer_formatter import build_safe_extractive_answer, top_confidence
from api.language import detect_question_language, resolve_response_language
from retrieval.answerability import apply_answerability_gate, assess_answerability
from retrieval.evidence_verifier import verify_chunks


def _verified_rows(question: str, contents: list[str]) -> list[dict]:
    rows = [
        {
            "chunkId": f"chunk-{index}",
            "documentName": f"doc-{index}.txt",
            "page": 1,
            "content": content,
            "score": 0.76 - (index * 0.03),
            "baseScore": 0.62 - (index * 0.02),
            "semanticScore": 0.62,
            "keywordScore": 0.55,
            "exactTokenCoverage": 0.45,
            "metadata": {"filename": f"doc-{index}.txt", "page": 1},
        }
        for index, content in enumerate(contents)
    ]
    return verify_chunks(question, rows, minimum_score=0.58)


def test_file_upload_question_rejects_mailbox_quota_evidence() -> None:
    question = "What is the maximum file-upload size in the customer portal?"
    rows = _verified_rows(
        question,
        ["Q: What is my mailbox size limit? A: The mailbox size limit is 50 GB."],
    )
    decision = assess_answerability(question, rows)
    assert decision.answerable is False
    assert apply_answerability_gate(question, rows) == []


def test_file_upload_question_accepts_coherent_portal_upload_evidence() -> None:
    question = "What is the maximum file-upload size in the customer portal?"
    rows = _verified_rows(
        question,
        ["The customer portal allows file uploads up to a maximum size of 25 MB."],
    )
    accepted = apply_answerability_gate(question, rows)
    assert accepted
    assert accepted[0]["answerabilityStrictlySupported"] is True
    assert accepted[0]["answerabilityCoherentEvidence"] is True


def test_mailbox_question_still_accepts_mailbox_evidence() -> None:
    question = "What is the mailbox size limit?"
    rows = _verified_rows(question, ["The mailbox size limit is 50 GB."])
    assert assess_answerability(question, rows).answerable is True


def test_p1_question_rejects_p2_deadline_relation() -> None:
    question = "How quickly must a P1 incident be resolved?"
    rows = _verified_rows(question, ["P2 incidents must be resolved within 8 hours."])
    assert assess_answerability(question, rows).answerable is False


def test_explicit_ui_language_overrides_question_detection() -> None:
    assert detect_question_language(
        "What is the maximum file-upload size in the customer portal?",
        fallback="ID",
    ) == "EN"
    assert resolve_response_language(
        "Berapa batas ukuran file yang dapat diunggah?",
        "EN",
    ) == "EN"
    assert resolve_response_language(
        "What is the maximum file-upload size in the customer portal?",
        "ID",
    ) == "ID"


def test_confidence_cannot_exceed_verified_source_quality() -> None:
    chunks = [
        {
            "chunkId": "mailbox",
            "content": "The mailbox size limit is 50 GB.",
            "documentName": "faq.txt",
            "metadata": {"filename": "faq.txt", "page": 1},
            "score": 0.46,
            "baseScore": 0.46,
            "semanticScore": 0.46,
            "keywordScore": 0.40,
            "evidenceScore": 0.58,
            "evidenceSupported": True,
            "answerabilityAccepted": True,
            "answerabilityStrictlySupported": True,
            "answerabilityEvidenceSelected": True,
            "answerabilityScore": 0.90,
            "answerabilityRequiresCoherentEvidence": True,
            "answerabilityCoherentEvidence": True,
            "contextSelected": True,
        }
    ]
    confidence = top_confidence(chunks, question="What is the mailbox size limit?")
    assert 0 < confidence <= 0.46


def test_extractive_fallback_refuses_unaccepted_bundle() -> None:
    answer = build_safe_extractive_answer(
        "What is the maximum file-upload size in the customer portal?",
        [
            {
                "content": "The mailbox size limit is 50 GB.",
                "score": 0.8,
                "evidenceSupported": False,
            }
        ],
        language="EN",
    )
    assert answer.startswith("The requested information was not found")


def test_chat_pipeline_rejects_mailbox_match_before_llm(monkeypatch) -> None:
    from api import chat_service

    question = "What is the maximum file-upload size in the customer portal?"
    rows = _verified_rows(
        question,
        ["Q: What is my mailbox size limit? A: The mailbox size limit is 50 GB."],
    )
    rejected = apply_answerability_gate(question, rows)
    assert rejected == []

    llm_called = {"value": False}

    def fake_llm(*args, **kwargs):
        llm_called["value"] = True
        return "This must never be returned."

    monkeypatch.setattr(chat_service, "hybrid_search", lambda *args, **kwargs: rejected)
    monkeypatch.setattr(chat_service, "build_grounded_answer", fake_llm)

    response = chat_service.run_chat(question, language="AUTO", model="groq")

    assert llm_called["value"] is False
    assert response["generation_mode"] == "retrieval_refusal"
    assert response["model"] == "retrieval-refusal"
    assert response["confidence"] == 0.0
    assert response["sources"] == []
    assert response["language"] == "EN"


def test_chat_pipeline_keeps_explicit_indonesian_output_after_strict_acceptance(monkeypatch) -> None:
    from api import chat_service

    question = "What is the maximum file-upload size in the customer portal?"
    rows = _verified_rows(
        question,
        ["The customer portal allows file uploads up to a maximum size of 25 MB."],
    )
    accepted = apply_answerability_gate(question, rows)
    assert accepted

    monkeypatch.setattr(chat_service, "hybrid_search", lambda *args, **kwargs: accepted)
    monkeypatch.setattr(
        chat_service,
        "build_grounded_answer",
        lambda *args, **kwargs: "Batas maksimal unggahan file di portal pelanggan adalah 25 MB.",
    )
    monkeypatch.setattr(chat_service, "build_dataset_follow_up_question", lambda **kwargs: None)

    response = chat_service.run_chat(question, language="ID", model="groq")

    assert response["generation_mode"] == "native_model"
    assert response["model"] == "groq-rag"
    assert response["language"] == "ID"
    assert "25 MB" in response["answer"]
    assert response["sources"]


def test_chat_pipeline_rejects_wrong_language_output(monkeypatch) -> None:
    from api import chat_service

    question = "Berapa batas maksimal unggahan file di portal pelanggan?"
    rows = _verified_rows(
        question,
        ["The customer portal allows file uploads up to a maximum size of 25 MB."],
    )
    accepted = apply_answerability_gate(question, rows)
    assert accepted

    monkeypatch.setattr(chat_service, "hybrid_search", lambda *args, **kwargs: accepted)
    monkeypatch.setattr(
        chat_service,
        "build_grounded_answer",
        lambda *args, **kwargs: "The maximum file upload size is 25 MB.",
    )
    monkeypatch.setattr(chat_service, "build_dataset_follow_up_question", lambda **kwargs: None)

    response = chat_service.run_chat(question, language="ID", model="groq")

    assert response["generation_mode"] == "retrieval_refusal"
    assert response["language"] == "ID"
    assert response["sources"] == []
    assert "The maximum" not in response["answer"]
