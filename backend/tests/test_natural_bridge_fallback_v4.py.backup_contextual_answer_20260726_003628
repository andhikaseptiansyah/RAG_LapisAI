from __future__ import annotations

from api import chat_service
from retrieval.query_expansion import (
    build_natural_bridge_query,
    build_query_variants,
)


QUESTION_ID = "Seberapa cepat insiden IT P1 harus diselesaikan?"
QUESTION_EN = "How quickly must a P1 IT incident be resolved?"
EVIDENCE = "P1 incidents must be acknowledged within 15 minutes and resolved within 4 hours."


def _accepted_chunk() -> dict:
    return {
        "chunkId": "p1",
        "documentName": "SOP_IT_Incident_Handling.pdf",
        "page": 1,
        "content": EVIDENCE,
        "score": 0.8716,
        "baseScore": 0.8716,
        "semanticScore": 0.82,
        "keywordScore": 1.0,
        "evidenceSupported": True,
        "evidenceScore": 0.90,
        "evidenceHardFailures": [],
        "evidenceHardContradictions": [],
        "answerabilityAccepted": True,
        "answerabilityStrictlySupported": True,
        "answerabilityEvidenceSelected": True,
        "answerabilityRequiresCoherentEvidence": True,
        "answerabilityCoherentEvidence": True,
        "answerabilityScore": 0.86,
        "contextSelected": True,
        "metadata": {
            "filename": "SOP_IT_Incident_Handling.pdf",
            "page": 1,
            "paragraph_start": 1,
            "paragraph_end": 8,
        },
    }


def test_natural_bridge_matches_the_manual_english_query_that_succeeds() -> None:
    assert build_natural_bridge_query(QUESTION_ID) == QUESTION_EN
    variants = build_query_variants(QUESTION_ID)
    assert variants[0] == QUESTION_ID
    assert variants[1] == QUESTION_EN


def test_chat_retries_natural_bridge_after_original_retrieval_refusal(monkeypatch) -> None:
    calls: list[str] = []

    def fake_hybrid_search(query: str, **kwargs):
        calls.append(query)
        if query == QUESTION_ID:
            return []
        if query == QUESTION_EN:
            return [_accepted_chunk()]
        return []

    # The bridge result is already strict. Keep the re-verification deterministic
    # in this unit test and assert that it is still performed for the original
    # question.
    def fake_reverify(question: str, candidates: list[dict], **kwargs):
        assert question == QUESTION_ID
        assert candidates[0]["chunkId"] == "p1"
        return candidates

    def fake_answerability(question: str, candidates: list[dict]):
        assert question == QUESTION_ID
        return [
            {
                **candidate,
                "evidenceSupported": True,
                "evidenceScore": 0.90,
                "evidenceHardFailures": [],
                "evidenceHardContradictions": [],
                "answerabilityAccepted": True,
                "answerabilityStrictlySupported": True,
                "answerabilityEvidenceSelected": True,
                "answerabilityRequiresCoherentEvidence": True,
                "answerabilityCoherentEvidence": True,
                "answerabilityScore": 0.86,
            }
            for candidate in candidates
        ]

    monkeypatch.setattr(chat_service, "hybrid_search", fake_hybrid_search)
    monkeypatch.setattr(chat_service, "_apply_evidence_verification", fake_reverify)
    monkeypatch.setattr(chat_service, "apply_answerability_gate", fake_answerability)
    monkeypatch.setattr(chat_service, "select_context_bundle", lambda *args, **kwargs: args[1])
    monkeypatch.setattr(chat_service, "build_grounded_answer", lambda *args, **kwargs: EVIDENCE)
    monkeypatch.setattr(chat_service, "build_dataset_follow_up_question", lambda **kwargs: None)

    response = chat_service.run_chat(QUESTION_ID, language="ID", model="ollama")

    assert calls == [QUESTION_ID, QUESTION_EN]
    assert response["retrieval_mode"] == "natural_language_bridge"
    assert response["retrieval_query"] == QUESTION_EN
    assert response["answer"] == "4 jam."
    assert response["sources"][0]["document_name"] == "SOP_IT_Incident_Handling.pdf"


def test_scalar_fallback_selects_p1_resolution_from_real_multi_priority_excerpt(monkeypatch) -> None:
    evidence = (
        "Response Targets P1 incidents must be acknowledged within 15 minutes "
        "and resolved within 4 hours. P2 incidents must be resolved within 8 hours."
    )
    chunk = _accepted_chunk()
    chunk["content"] = evidence

    calls: list[str] = []

    def fake_hybrid_search(query: str, **kwargs):
        calls.append(query)
        if query == QUESTION_ID:
            return []
        if query == QUESTION_EN:
            return [chunk]
        return []

    monkeypatch.setattr(chat_service, "hybrid_search", fake_hybrid_search)
    monkeypatch.setattr(chat_service, "_apply_evidence_verification", lambda q, rows, **k: rows)
    monkeypatch.setattr(
        chat_service,
        "apply_answerability_gate",
        lambda q, rows: [
            {
                **row,
                "evidenceSupported": True,
                "evidenceScore": 0.90,
                "evidenceHardFailures": [],
                "evidenceHardContradictions": [],
                "answerabilityAccepted": True,
                "answerabilityStrictlySupported": True,
                "answerabilityEvidenceSelected": True,
                "answerabilityRequiresCoherentEvidence": True,
                "answerabilityCoherentEvidence": True,
                "answerabilityScore": 0.86,
            }
            for row in rows
        ],
    )
    monkeypatch.setattr(chat_service, "select_context_bundle", lambda *args, **kwargs: args[1])
    monkeypatch.setattr(chat_service, "build_grounded_answer", lambda *args, **kwargs: evidence)
    monkeypatch.setattr(chat_service, "build_dataset_follow_up_question", lambda **kwargs: None)

    response = chat_service.run_chat(QUESTION_ID, language="ID", model="ollama")

    assert calls == [QUESTION_ID, QUESTION_EN]
    assert response["answer"] == "4 jam."
    assert response["retrieval_mode"] == "natural_language_bridge"


def test_real_evidence_and_answerability_gates_accept_bridge_candidate(monkeypatch) -> None:
    evidence = (
        "Response Targets P1 incidents must be acknowledged within 15 minutes "
        "and resolved within 4 hours. P2 incidents must be resolved within 8 hours."
    )
    candidate = {
        "chunkId": "p1-real-gates",
        "documentName": "SOP_IT_Incident_Handling.pdf",
        "page": 1,
        "content": evidence,
        "score": 0.8716,
        "baseScore": 0.8716,
        "semanticScore": 0.8716,
        "keywordScore": 0.80,
        "rerankerApplied": True,
        "rerankerScore": 0.8716,
        "metadata": {
            "filename": "SOP_IT_Incident_Handling.pdf",
            "page": 1,
            "paragraph_start": 1,
            "paragraph_end": 8,
            "content": evidence,
        },
    }

    def fake_hybrid_search(query: str, **kwargs):
        if query == QUESTION_ID:
            return []
        if query == QUESTION_EN:
            return [candidate]
        return []

    monkeypatch.setattr(chat_service, "hybrid_search", fake_hybrid_search)
    monkeypatch.setattr(chat_service, "build_grounded_answer", lambda *args, **kwargs: evidence)
    monkeypatch.setattr(chat_service, "build_dataset_follow_up_question", lambda **kwargs: None)

    response = chat_service.run_chat(QUESTION_ID, language="ID", model="ollama")

    assert response["answer"] == "4 jam."
    assert response["retrieval_mode"] == "natural_language_bridge"
    assert response["retrieval_query"] == QUESTION_EN
    assert response["confidence"] >= 0.50
    assert response["sources"][0]["document_name"] == "SOP_IT_Incident_Handling.pdf"
