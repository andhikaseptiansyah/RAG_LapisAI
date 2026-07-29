from __future__ import annotations

from api import chat_service


QUESTION_ID = "Seberapa cepat insiden IT P1 harus diselesaikan?"
QUESTION_EN = "How quickly must a P1 IT incident be resolved?"
EVIDENCE = (
    "Response Targets P1 incidents must be acknowledged within 15 minutes "
    "and resolved within 4 hours."
)


def test_indonesian_p1_reuses_successful_english_path_and_returns_localized_answer(monkeypatch) -> None:
    candidate = {
        "chunkId": "sop-p1-page-1",
        "documentName": "SOP_IT_Incident_Handling.pdf",
        "page": 1,
        "content": EVIDENCE,
        "score": 0.89,
        "baseScore": 0.84,
        "semanticScore": 0.82,
        "keywordScore": 1.0,
        "rerankerScore": 0.89,
        # Simulate stale annotations produced by an earlier pass. V7 must clear
        # these before validating the original Indonesian question.
        "evidenceSupported": False,
        "evidenceScore": 0.0,
        "evidenceHardFailures": ["stale_failure"],
        "answerabilityAccepted": False,
        "answerabilityStrictlySupported": False,
        "metadata": {
            "filename": "SOP_IT_Incident_Handling.pdf",
            "page": 1,
            "paragraph_start": 1,
            "paragraph_end": 8,
        },
    }
    calls: list[tuple[str, bool | None]] = []

    def fake_hybrid_search(query: str, **kwargs):
        calls.append((query, kwargs.get("apply_answerability")))
        if query == QUESTION_ID:
            return []
        if query == QUESTION_EN:
            return [candidate]
        return []

    monkeypatch.setattr(chat_service, "hybrid_search", fake_hybrid_search)
    monkeypatch.setattr(chat_service, "select_context_bundle", lambda *args, **kwargs: args[1])
    monkeypatch.setattr(chat_service, "build_grounded_answer", lambda *args, **kwargs: EVIDENCE)
    monkeypatch.setattr(chat_service, "build_dataset_follow_up_question", lambda **kwargs: None)

    response = chat_service.run_chat(QUESTION_ID, language="ID", model="ollama")

    assert calls[0][0] == QUESTION_ID
    assert calls[1] == (QUESTION_EN, True)
    assert response["answer"] == "4 jam."
    assert response["language"] == "ID"
    assert response["retrieval_mode"] == "natural_language_bridge"
    assert response["retrieval_query"] == QUESTION_EN
    assert response["failure_stage"] is None
    assert response["sources"][0]["document_name"] == "SOP_IT_Incident_Handling.pdf"
