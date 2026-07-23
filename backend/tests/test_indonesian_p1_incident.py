from __future__ import annotations

from unittest.mock import patch

from retrieval.answerability import assess_answerability
from retrieval.evidence_verifier import verify_chunks, verify_evidence
from retrieval.hybrid_search import _apply_evidence_verification, _base_hybrid_candidates
from retrieval.query_expansion import concepts_in_text, expand_query


QUESTION_ID = "Seberapa cepat insiden IT P1 harus diselesaikan?"
P1_EVIDENCE_EN = "P1 IT incidents must be resolved within 4 hours."
P2_EVIDENCE_EN = "P2 IT incidents must be resolved within 8 hours."


def test_indonesian_p1_word_order_is_recognized_and_expanded() -> None:
    concepts = set(concepts_in_text(QUESTION_ID))
    expanded = expand_query(QUESTION_ID).lower()

    assert {"incident_p1", "processing_time"}.issubset(concepts)
    assert "p1 it incident" in expanded
    assert "resolution time" in expanded
    assert "resolved within" in expanded


def test_english_p1_evidence_matches_the_same_canonical_concepts() -> None:
    concepts = set(concepts_in_text(P1_EVIDENCE_EN))
    assert {"incident_p1", "processing_time"}.issubset(concepts)

    decision = verify_evidence(
        QUESTION_ID,
        P1_EVIDENCE_EN,
        semantic_score=0.30,
    )
    assert decision.supported, decision
    assert decision.score >= 0.58
    assert not decision.hard_failures


def test_p2_evidence_cannot_answer_a_p1_question() -> None:
    decision = verify_evidence(
        QUESTION_ID,
        P2_EVIDENCE_EN,
        semantic_score=0.95,
    )
    assert not decision.supported
    assert any(
        item.startswith("missing_concept:incident_p1")
        or item.startswith("conflicting_concept:incident_p2")
        for item in decision.hard_failures
    )


def test_p1_cross_language_candidate_survives_existing_gates_without_lowering_thresholds() -> None:
    semantic_rows = [
        {
            "chunkId": "p1",
            "content": P1_EVIDENCE_EN,
            "metadata": {"filename": "SOP_IT_Incident_Handling.pdf", "page": 1},
            "semanticScore": 0.30,
            "semanticRank": 0,
            "expandedQuery": expand_query(QUESTION_ID),
        }
    ]
    keyword_rows = [
        {
            "chunkId": "p1",
            "content": P1_EVIDENCE_EN,
            "metadata": {"filename": "SOP_IT_Incident_Handling.pdf", "page": 1},
            "keywordScore": 0.34,
            "keywordRank": 0,
            "expandedQuery": expand_query(QUESTION_ID),
        }
    ]

    with patch("retrieval.hybrid_search.semantic_search", return_value=semantic_rows), patch(
        "retrieval.hybrid_search.bm25_search", return_value=keyword_rows
    ):
        candidates = _base_hybrid_candidates(QUESTION_ID, candidate_k=20)

    verified = _apply_evidence_verification(
        QUESTION_ID,
        candidates,
        min_score=0.24,
    )
    decision = assess_answerability(QUESTION_ID, verified)

    assert verified
    assert verified[0]["evidenceSupported"] is True
    assert verified[0]["evidenceScore"] >= 0.58
    assert decision.answerable, decision


def test_verify_chunks_preserves_p1_subject_and_duration_support() -> None:
    rows = verify_chunks(
        QUESTION_ID,
        [
            {
                "chunkId": "p1",
                "content": P1_EVIDENCE_EN,
                "score": 0.62,
                "baseScore": 0.42,
                "semanticScore": 0.30,
                "keywordScore": 0.67,
            }
        ],
    )

    assert rows[0]["evidenceSupported"] is True
    assert rows[0]["evidenceMissingConcepts"] == []
    assert rows[0]["evidenceContradictions"] == []


def test_chat_returns_localized_verified_duration_when_model_repeats_english(monkeypatch) -> None:
    from api import chat_service

    chunks = [
        {
            "chunkId": "p1",
            "documentName": "SOP_IT_Incident_Handling.pdf",
            "page": 1,
            "content": P1_EVIDENCE_EN,
            "score": 0.67,
            "baseScore": 0.52,
            "semanticScore": 0.30,
            "keywordScore": 1.0,
            "evidenceSupported": True,
            "evidenceScore": 0.775,
            "evidenceHardFailures": [],
            "evidenceHardContradictions": [],
            "answerabilityAccepted": True,
            "answerabilityStrictlySupported": True,
            "answerabilityEvidenceSelected": True,
            "answerabilityRequiresCoherentEvidence": True,
            "answerabilityCoherentEvidence": True,
            "answerabilityScore": 0.82,
            "contextSelected": True,
            "metadata": {
                "filename": "SOP_IT_Incident_Handling.pdf",
                "page": 1,
                "paragraph_start": 1,
                "paragraph_end": 8,
            },
        }
    ]

    monkeypatch.setattr(chat_service, "hybrid_search", lambda *args, **kwargs: chunks)
    monkeypatch.setattr(chat_service, "select_context_bundle", lambda *args, **kwargs: chunks)
    monkeypatch.setattr(
        chat_service,
        "build_grounded_answer",
        lambda *args, **kwargs: P1_EVIDENCE_EN,
    )
    monkeypatch.setattr(
        chat_service,
        "build_dataset_follow_up_question",
        lambda **kwargs: None,
    )

    response = chat_service.run_chat(QUESTION_ID, language="ID", model="ollama")

    assert response["generation_mode"] == "extractive_fallback"
    assert response["language"] == "ID"
    assert response["answer"] == "4 jam."
    assert response["sources"]
    assert response["sources"][0]["document_name"] == "SOP_IT_Incident_Handling.pdf"
