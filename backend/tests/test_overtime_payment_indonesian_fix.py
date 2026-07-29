from api.answer_formatter import build_safe_extractive_answer
from retrieval.answerability import assess_answerability
from retrieval.query_expansion import build_natural_bridge_query, concepts_in_text
from retrieval.requirements import extract_evidence_requirements, requirement_satisfied


QUESTION = "Kapan lembur yang telah disetujui akan dibayarkan?"
EVIDENCE = (
    "## Overtime Q: How is overtime paid? "
    "A: Approved overtime is paid in the following month's payroll."
)


def _candidate():
    return {
        "chunkId": "faq-payroll-overtime",
        "documentName": "FAQ_Payroll.txt",
        "content": EVIDENCE,
        "score": 0.83,
        "baseScore": 0.83,
        "semanticScore": 0.82,
        "keywordScore": 0.75,
        "exactTokenCoverage": 0.75,
        "evidenceScore": 0.90,
        "evidenceSupported": True,
        "answerabilityAccepted": True,
        "answerabilityEvidenceSelected": True,
        "answerabilityStrictlySupported": True,
        "answerabilityRequiresCoherentEvidence": True,
        "answerabilityCoherentEvidence": True,
    }


def test_overtime_is_a_hard_subject_concept():
    assert "overtime_payment" in concepts_in_text(QUESTION)
    assert "approved overtime" in build_natural_bridge_query(QUESTION).lower()


def test_relative_payroll_cycle_satisfies_when_requirement():
    requirements = extract_evidence_requirements(QUESTION)
    date_requirement = next(item for item in requirements if item.kind == "date_or_time")
    assert requirement_satisfied(date_requirement, [EVIDENCE])


def test_pre_rerank_answerability_accepts_exact_overtime_evidence():
    decision = assess_answerability(QUESTION, [_candidate()])
    assert decision.answerable, decision.reason
    assert "supported_evidence" in decision.passed_checks
    assert "concept:overtime_payment" in decision.passed_checks


def test_indonesian_extractive_fallback_is_localized_and_explained():
    answer = build_safe_extractive_answer(QUESTION, [_candidate()], language="ID")
    assert "bulan berikutnya" in answer.lower()
    assert "lembur yang telah disetujui" in answer.lower()
    assert "periode payroll" in answer.lower()
