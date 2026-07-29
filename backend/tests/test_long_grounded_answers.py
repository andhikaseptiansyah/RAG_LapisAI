from api import chat_service
from api.answer_formatter import build_evidence_excerpt, build_generation_evidence
from api.grounding_validator import validate_grounded_answer
from api.llm_shared import build_system_prompt, build_user_prompt
from retrieval.context_selector import select_context_bundle


QUESTION = "Berapa nilai RTO dan RPO pada rencana pemulihan bencana?"


def _row(content: str, score: float, document: str) -> dict:
    return {
        "chunkId": f"{document}-{score}",
        "documentName": document,
        "content": content,
        "score": score,
        "evidenceSupported": True,
    }


def _strict_row(content: str, score: float, document: str) -> dict:
    return {
        **_row(content, score, document),
        "baseScore": score,
        "semanticScore": score,
        "keywordScore": score,
        "evidenceScore": score,
        "evidenceHardFailures": [],
        "evidenceHardContradictions": [],
        "answerabilityAccepted": True,
        "answerabilityStrictlySupported": True,
        "answerabilityEvidenceSelected": True,
        "answerabilityRequiresCoherentEvidence": False,
        "answerabilityScore": score,
        "metadata": {"filename": document, "paragraph_start": 1, "paragraph_end": 2},
    }


def test_generation_keeps_relevant_supporting_sentences_beyond_citation_excerpt() -> None:
    content = (
        "Rencana pemulihan bencana menetapkan RTO 4 jam dan RPO 1 jam. "
        "RTO menunjukkan batas waktu pemulihan layanan setelah gangguan. "
        "RPO menunjukkan batas kehilangan data yang masih dapat diterima."
    )

    citation_excerpt = build_evidence_excerpt(QUESTION, content)
    generation_evidence = build_generation_evidence(QUESTION, content)

    assert len(generation_evidence) >= len(citation_excerpt)
    assert "batas waktu pemulihan layanan" in generation_evidence
    assert "batas kehilangan data" in generation_evidence


def test_prompt_requests_longer_paragraph_only_when_evidence_supports_it() -> None:
    system_prompt = build_system_prompt("ID")
    user_prompt = build_user_prompt(QUESTION, "[EVIDENCE 1]\nRTO 4 jam.", "ID")

    assert "2 to 4 informative sentences" in system_prompt
    assert "2 sampai 4 kalimat" in user_prompt
    assert "generic closing" in system_prompt
    assert "paling singkat" not in user_prompt


def test_selector_adds_a_second_relevant_source_but_not_unrelated_padding() -> None:
    selected = select_context_bundle(
        QUESTION,
        [
            _row(
                "Rencana pemulihan bencana menetapkan RTO 4 jam dan RPO 1 jam.",
                0.93,
                "TECH_Disaster_Recovery.txt",
            ),
            _row(
                "Kebijakan pemulihan bencana menjelaskan RTO sebagai batas waktu pemulihan layanan.",
                0.88,
                "BCP_Glossary.pdf",
            ),
            _row(
                "Karyawan dapat mengajukan penggantian biaya perjalanan dinas.",
                0.90,
                "Travel_Policy.pdf",
            ),
        ],
        max_contexts=4,
        minimum_contexts=2,
    )

    assert [item["documentName"] for item in selected] == [
        "TECH_Disaster_Recovery.txt",
        "BCP_Glossary.pdf",
    ]


def test_chat_returns_supported_paragraph_and_two_relevant_sources(monkeypatch) -> None:
    chunks = [
        _strict_row(
            "Rencana pemulihan bencana menetapkan RTO 4 jam dan RPO 1 jam.",
            0.93,
            "TECH_Disaster_Recovery.txt",
        ),
        _strict_row(
            "Kebijakan pemulihan bencana menjelaskan RTO sebagai batas waktu pemulihan "
            "layanan dan RPO sebagai batas kehilangan data yang dapat diterima.",
            0.88,
            "BCP_Glossary.pdf",
        ),
    ]
    expected_answer = (
        "Rencana pemulihan bencana menetapkan RTO 4 jam dan RPO 1 jam. "
        "RTO merupakan batas waktu pemulihan layanan setelah gangguan. "
        "RPO merupakan batas kehilangan data yang masih dapat diterima."
    )

    monkeypatch.setattr(chat_service, "hybrid_search", lambda *args, **kwargs: chunks)
    monkeypatch.setattr(chat_service, "build_grounded_answer", lambda *args, **kwargs: expected_answer)
    monkeypatch.setattr(chat_service, "build_dataset_follow_up_question", lambda **kwargs: None)

    response = chat_service.run_chat(QUESTION, language="ID", model="ollama")

    assert response["answer"] == expected_answer
    assert response["generation_mode"] == "native_model"
    assert len(response["sources"]) == 2
    assert {source["document_name"] for source in response["sources"]} == {
        "TECH_Disaster_Recovery.txt",
        "BCP_Glossary.pdf",
    }


def test_grounding_accepts_expanded_indonesian_p1_answer() -> None:
    evidence = (
        "P1 incidents must be acknowledged within 15 minutes and resolved within "
        "4 hours. If a P1 is not resolved within 2 hours, it is escalated to the "
        "Head of Infrastructure."
    )
    answer = (
        "Insiden IT P1 harus diselesaikan dalam 4 jam. Insiden tersebut juga harus "
        "diakui dalam 15 menit. Jika belum diselesaikan dalam 2 jam, insiden akan "
        "dieskalasikan kepada Head of Infrastructure."
    )

    decision = validate_grounded_answer(
        "Seberapa cepat insiden IT P1 harus diselesaikan?",
        answer,
        [_strict_row(evidence, 0.90, "SOP_IT_Incident_Handling.pdf")],
    )

    assert decision.supported, decision


def test_grounding_accepts_probation_translation_with_evaluation_detail() -> None:
    evidence = (
        "New employees serve a probation period of 3 months. A formal performance "
        "evaluation is conducted in week 12 before confirmation."
    )
    answer = (
        "Masa percobaan karyawan baru berlangsung selama 3 bulan. Evaluasi kinerja "
        "formal dilakukan pada minggu ke-12 sebelum konfirmasi."
    )

    decision = validate_grounded_answer(
        "Berapa lama masa percobaan untuk karyawan baru?",
        answer,
        [_strict_row(evidence, 0.90, "SOP_Onboarding.pdf")],
    )

    assert decision.supported, decision


def test_grounding_still_rejects_an_invented_incident_actor() -> None:
    evidence = (
        "P1 incidents must be acknowledged within 15 minutes and resolved within "
        "4 hours."
    )
    answer = (
        "Insiden IT P1 harus diselesaikan dalam waktu maksimal 4 jam. Tim eksternal "
        "wajib memberikan pengakuan awal dalam 15 menit."
    )

    decision = validate_grounded_answer(
        "Seberapa cepat insiden IT P1 harus diselesaikan?",
        answer,
        [_strict_row(evidence, 0.90, "SOP_IT_Incident_Handling.pdf")],
    )

    assert not decision.supported
    assert any("Tim eksternal" in claim for claim in decision.unsupported_claims)
