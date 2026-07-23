from __future__ import annotations

from api import chat_service


QUESTION_ID = "Seberapa cepat insiden IT P1 harus diselesaikan?"
BRIDGE_QUERY = "How quickly must a P1 IT incident be resolved?"
P1_EVIDENCE = "P1 IT incidents must be resolved within 4 hours."


def _strict_candidate() -> dict:
    return {
        "chunkId": "p1",
        "documentName": "SOP_IT_Incident_Handling.pdf",
        "page": 1,
        "content": P1_EVIDENCE,
        "score": 0.72,
        "baseScore": 0.61,
        "evidenceSupported": True,
        "evidenceScore": 0.81,
        "evidenceHardFailures": [],
        "evidenceHardContradictions": [],
        "answerabilityAccepted": True,
        "answerabilityStrictlySupported": True,
        "answerabilityEvidenceSelected": True,
        "answerabilityRequiresCoherentEvidence": True,
        "answerabilityCoherentEvidence": True,
        "metadata": {
            "filename": "SOP_IT_Incident_Handling.pdf",
            "page": 1,
        },
    }


def test_bridge_runs_when_primary_candidates_exist_but_are_not_strict(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []
    weak_primary = {
        "chunkId": "weak",
        "content": "General incident handling policy.",
        "score": 0.55,
        "answerabilityAccepted": False,
    }
    bridge_raw = {
        "chunkId": "p1",
        "content": P1_EVIDENCE,
        "score": 0.72,
        "baseScore": 0.61,
        "metadata": {
            "filename": "SOP_IT_Incident_Handling.pdf",
            "page": 1,
        },
    }

    def fake_hybrid_search(query: str, **kwargs):
        calls.append((query, kwargs))
        if query == QUESTION_ID:
            return [weak_primary]
        if query == BRIDGE_QUERY:
            return [bridge_raw]
        return []

    monkeypatch.setattr(chat_service, "hybrid_search", fake_hybrid_search)
    monkeypatch.setattr(
        chat_service,
        "_apply_evidence_verification",
        lambda question, candidates, min_score: [_strict_candidate()],
    )
    monkeypatch.setattr(
        chat_service,
        "apply_answerability_gate",
        lambda question, candidates: candidates,
    )

    rows, mode, retrieval_query = chat_service._retrieve_with_language_fallback(
        QUESTION_ID,
        top_k=5,
    )

    assert mode == "natural_language_bridge"
    assert retrieval_query == BRIDGE_QUERY
    assert rows and rows[0]["chunkId"] == "p1"
    assert rows[0]["retrievalFallbackApplied"] is True
    assert calls[0][0] == QUESTION_ID
    assert calls[1][0] == BRIDGE_QUERY
    assert calls[1][1]["apply_answerability"] is False
    assert calls[1][1]["candidate_k"] >= 40


def test_strict_primary_result_does_not_run_bridge(monkeypatch) -> None:
    calls: list[str] = []
    strict = _strict_candidate()

    def fake_hybrid_search(query: str, **kwargs):
        calls.append(query)
        return [strict]

    monkeypatch.setattr(chat_service, "hybrid_search", fake_hybrid_search)

    rows, mode, retrieval_query = chat_service._retrieve_with_language_fallback(
        QUESTION_ID,
        top_k=5,
    )

    assert rows == [strict]
    assert mode == "original"
    assert retrieval_query == QUESTION_ID
    assert calls == [QUESTION_ID]
