from __future__ import annotations

from api import chat_service
from api.answer_formatter import build_verified_scalar_answer
from api.grounding_validator import validate_grounded_answer


QUESTION_ID = "Seberapa cepat insiden IT P1 harus diselesaikan?"
EVIDENCE_MERGED = (
    "Response Targets P1 incidents must be acknowledged within 15 minutes "
    "and resolved within 4 hours P2 incidents must be acknowledged within "
    "30 minutes and resolved within 8 hours"
)


def _strict_chunk() -> dict:
    return {
        "chunkId": "sop-p1-page-1",
        "documentName": "SOP_IT_Incident_Handling.pdf",
        "page": 1,
        "content": EVIDENCE_MERGED,
        "score": 0.831,
        "baseScore": 0.80,
        "semanticScore": 0.82,
        "keywordScore": 1.0,
        "rerankerScore": 0.89,
        "evidenceSupported": True,
        "evidenceScore": 0.84,
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


def test_grounding_accepts_faithful_indonesian_translation_of_english_evidence() -> None:
    decision = validate_grounded_answer(
        QUESTION_ID,
        "Insiden IT P1 harus diselesaikan dalam 4 jam.",
        [_strict_chunk()],
    )
    assert decision.supported, decision


def test_grounding_still_rejects_an_unsupported_explanatory_tail() -> None:
    decision = validate_grounded_answer(
        QUESTION_ID,
        "Insiden IT P1 harus diselesaikan dalam 4 jam untuk kepuasan pelanggan.",
        [_strict_chunk()],
    )
    assert not decision.supported
    assert "unsupported_claims" in decision.reasons


def test_verified_scalar_selects_p1_resolution_from_merged_p1_p2_pdf_row() -> None:
    assert build_verified_scalar_answer(
        QUESTION_ID,
        [_strict_chunk()],
        language="ID",
    ) == "4 jam."


def test_chat_returns_verified_scalar_without_calling_ollama(monkeypatch) -> None:
    chunk = _strict_chunk()
    monkeypatch.setattr(chat_service, "hybrid_search", lambda *args, **kwargs: [chunk])
    monkeypatch.setattr(chat_service, "select_context_bundle", lambda *args, **kwargs: [chunk])
    monkeypatch.setattr(
        chat_service,
        "build_grounded_answer",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Ollama must not be called for one verified duration")
        ),
    )
    monkeypatch.setattr(chat_service, "build_dataset_follow_up_question", lambda **kwargs: None)

    response = chat_service.run_chat(QUESTION_ID, language="ID", model="ollama")

    assert response["answer"] == "4 jam."
    assert response["generation_mode"] == "verified_scalar"
    assert response["language"] == "ID"
    assert response["failure_stage"] is None
    assert response["sources"][0]["document_name"] == "SOP_IT_Incident_Handling.pdf"
