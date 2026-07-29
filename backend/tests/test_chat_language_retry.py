from __future__ import annotations

from api import chat_service


def _accepted_chunk() -> dict:
    return {
        "chunkId": "remote-work",
        "documentName": "employee-policy.txt",
        "page": 1,
        "content": (
            "Employees may work remotely for up to two days per week with "
            "their manager's approval."
        ),
        "score": 0.72,
        "baseScore": 0.68,
        "semanticScore": 0.68,
        "keywordScore": 0.0,
        "evidenceSupported": True,
        "evidenceScore": 0.64,
        "evidenceHardFailures": [],
        "evidenceHardContradictions": [],
        "answerabilityAccepted": True,
        "answerabilityStrictlySupported": True,
        "answerabilityEvidenceSelected": True,
        "answerabilityRequiresCoherentEvidence": False,
        "contextSelected": True,
        "metadata": {
            "filename": "employee-policy.txt",
            "page": 1,
        },
    }


def test_wrong_source_language_gets_a_minimal_evidence_retry(monkeypatch) -> None:
    question = "Berapa hari per minggu karyawan dapat bekerja dari rumah?"
    chunks = [_accepted_chunk()]
    generated_answers = iter(
        [
            "Employees may work remotely for up to two days per week.",
            "Karyawan dapat bekerja dari rumah paling banyak dua hari per minggu.",
        ]
    )
    call_count = {"value": 0}

    def fake_generation(*args, **kwargs):
        call_count["value"] += 1
        return next(generated_answers)

    monkeypatch.setattr(chat_service, "hybrid_search", lambda *args, **kwargs: chunks)
    monkeypatch.setattr(chat_service, "select_context_bundle", lambda *args, **kwargs: chunks)
    monkeypatch.setattr(chat_service, "build_grounded_answer", fake_generation)
    monkeypatch.setattr(chat_service, "build_dataset_follow_up_question", lambda **kwargs: None)

    response = chat_service.run_chat(question, language="ID", model="ollama")

    assert call_count["value"] == 2
    assert response["language"] == "ID"
    assert response["generation_mode"] == "language_repair_retry"
    assert "dua hari" in response["answer"].lower()
    assert response["sources"]
