from api.answer_formatter import build_safe_extractive_answer
from retrieval.answerability import assess_answerability
from retrieval.evidence_verifier import verify_chunks
from retrieval.query_expansion import build_natural_bridge_query, concepts_in_text


QUESTION = "Apakah perusahaan memberikan manfaat pensiun bagi karyawan?"
QUESTION_ONLY = (
    "A: Employees and up to 3 dependents are covered by the company health "
    "insurance plan. ## Pension Q: Is there a pension benefit?"
)
ANSWER_ONLY = (
    "A: The company contributes to BPJS Ketenagakerjaan for all employees."
)


def _candidate(content: str, chunk_id: str, chunk_index: int, score: float):
    return {
        "chunkId": chunk_id,
        "chunkIndex": chunk_index,
        "documentName": "FAQ_Benefits.txt",
        "content": content,
        "score": score,
        "baseScore": score,
        "semanticScore": score,
        "keywordScore": 0.70,
        "exactTokenCoverage": 0.70,
        "metadata": {
            "filename": "FAQ_Benefits.txt",
            "paragraph_start": 1,
            "chunk_index": chunk_index,
        },
    }


def test_pension_is_a_hard_cross_language_concept():
    assert "retirement_benefit" in concepts_in_text(QUESTION)
    bridge = build_natural_bridge_query(QUESTION).lower()
    assert "pension benefit" in bridge


def test_question_only_faq_chunk_is_not_supporting_evidence():
    chunk = verify_chunks(QUESTION, [_candidate(QUESTION_ONLY, "benefits-c0", 0, 0.73)])[0]
    assert chunk["evidenceSupported"] is False
    assert "faq_question_without_answer" in chunk["evidenceMissingRequirements"]


def test_bpjs_answer_chunk_is_supporting_evidence():
    from retrieval.evidence_verifier import verify_evidence

    decision = verify_evidence(QUESTION, ANSWER_ONLY, semantic_score=0.72)
    assert decision.supported is True
    assert "retirement_benefit" in decision.matched_concepts


def test_pre_rerank_answerability_uses_adjacent_answer_chunk():
    candidates = verify_chunks(
        QUESTION,
        [
            _candidate(QUESTION_ONLY, "benefits-c0", 0, 0.73),
            _candidate(ANSWER_ONLY, "benefits-c1", 1, 0.72),
        ],
    )
    decision = assess_answerability(QUESTION, candidates)
    assert decision.answerable, decision.reason
    assert "benefits-c1" in decision.evidence_chunk_ids
    assert "concept:retirement_benefit" in decision.passed_checks


def test_indonesian_fallback_answers_with_supported_bpjs_fact():
    chunk = verify_chunks(QUESTION, [_candidate(ANSWER_ONLY, "benefits-c1", 1, 0.83)])[0]
    chunk.update({
        "answerabilityAccepted": True,
        "answerabilityEvidenceSelected": True,
        "answerabilityStrictlySupported": True,
        "answerabilityRequiresCoherentEvidence": True,
        "answerabilityCoherentEvidence": True,
    })
    answer = build_safe_extractive_answer(QUESTION, [chunk], language="ID")
    assert answer.startswith("Ya.")
    assert "BPJS Ketenagakerjaan" in answer
    assert "seluruh karyawan" in answer
    assert "manfaat pensiun" in answer.lower()
