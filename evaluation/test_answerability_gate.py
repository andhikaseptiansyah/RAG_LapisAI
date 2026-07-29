from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from retrieval.answerability import apply_answerability_gate, assess_answerability


def candidate(
    content: str,
    *,
    score: float = 0.78,
    evidence_score: float = 0.82,
    supported: bool = True,
    exact: float = 0.35,
) -> dict:
    return {
        "chunkId": "test-1",
        "documentName": "test.txt",
        "page": "1",
        "content": content,
        "score": score,
        "baseScore": score,
        "semanticScore": score,
        "keywordScore": 0.5,
        "exactTokenCoverage": exact,
        "evidenceScore": evidence_score,
        "evidenceSupported": supported,
        "evidenceHardFailures": [],
    }


def test_regular_answerable_password_question_passes() -> None:
    question = "Bagaimana prosedur reset password dan berapa lama prosesnya?"
    rows = [
        candidate(
            "Raise a ticket to the IT Helpdesk via the portal. Password resets are processed within 1x24 hours."
        )
    ]
    decision = assess_answerability(question, rows)
    assert decision.answerable, decision
    assert apply_answerability_gate(question, rows)


def test_exact_url_question_is_rejected_without_literal_url() -> None:
    question = "Apa URL endpoint persis untuk self-service password reset Active Directory?"
    rows = [
        candidate(
            "Employees can reset a forgotten password by raising a ticket through the IT Helpdesk portal."
        )
    ]
    decision = assess_answerability(question, rows)
    assert not decision.answerable
    assert "explicit_url_or_endpoint" in decision.failed_checks
    assert apply_answerability_gate(question, rows) == []


def test_exact_url_question_passes_with_literal_url() -> None:
    question = "Apa URL endpoint persis untuk self-service password reset Active Directory?"
    rows = [
        candidate(
            "Use the self-service endpoint https://it.example.local/ad/reset to reset an Active Directory password."
        )
    ]
    decision = assess_answerability(question, rows)
    assert decision.answerable, decision


def test_paternity_question_does_not_accept_maternity_policy() -> None:
    question = "Berapa hari paternity leave untuk karyawan pria ketika pasangannya melahirkan?"
    rows = [candidate("Female employees receive paid maternity leave after childbirth.")]
    decision = assess_answerability(question, rows)
    assert not decision.answerable
    assert "missing_concept:paternity_leave" in decision.failed_checks


def test_frequency_question_requires_explicit_cadence() -> None:
    question = "Seberapa sering 'Full Datacenter Failover Exercise' dijalankan untuk menguji RTO?"
    rows = [candidate("The disaster recovery plan defines RTO and RPO targets for critical systems.")]
    decision = assess_answerability(question, rows)
    assert not decision.answerable
    assert "explicit_frequency" in decision.failed_checks
    assert any(item.startswith("quoted_phrase:") for item in decision.failed_checks)


def test_monetary_threshold_requires_currency_amount() -> None:
    question = "Berapa nilai nominal maksimum dalam Rupiah untuk menerima hadiah dari vendor?"
    rows = [candidate("Employees must disclose gifts received from suppliers and vendors.")]
    decision = assess_answerability(question, rows)
    assert not decision.answerable
    assert "explicit_monetary_value" in decision.failed_checks


def test_explicit_numeric_constraints_must_be_in_evidence() -> None:
    question = "Bagaimana mengarsipkan email yang lebih tua dari 3 tahun saat mailbox mendekati 50 GB?"
    rows = [candidate("Users can contact IT Support for mailbox and email archiving assistance.")]
    decision = assess_answerability(question, rows)
    assert not decision.answerable
    assert "explicit_constraint:3_years" in decision.failed_checks
    assert "explicit_constraint:50_gb" in decision.failed_checks




def test_compliance_scenario_uses_policy_threshold_not_literal_value() -> None:
    question = (
        "Jika saya membuat kredensial akun sepanjang 10 karakter, "
        "mengandung angka, huruf besar, dan simbol, apakah itu sudah "
        "mematuhi standar keamanan perusahaan?"
    )
    rows = [
        candidate(
            "Passwords must be at least 12 characters and include upper case, "
            "lower case, a number, and a symbol. Passwords must be changed "
            "every 90 days.",
            score=0.82,
            evidence_score=0.88,
            exact=0.45,
        )
    ]
    decision = assess_answerability(question, rows)
    assert decision.answerable, decision
    assert "explicit_constraint:10_characters" not in decision.failed_checks
    assert "scenario_threshold:length" in decision.passed_checks


def test_compliance_percentage_can_be_compared_with_different_threshold() -> None:
    question = (
        "If an automated testing suite reports 75% execution against the "
        "codebase, will the CI/CD pipeline allow the branch integration?"
    )
    rows = [
        candidate(
            "The CI/CD pipeline requires at least 80% unit test coverage "
            "before a branch can be merged.",
            score=0.80,
            evidence_score=0.86,
            exact=0.40,
        )
    ]
    decision = assess_answerability(question, rows)
    assert decision.answerable, decision
    assert "scenario_threshold:percentage" in decision.passed_checks

def test_high_reranker_score_cannot_rescue_weak_hybrid_candidate() -> None:
    question = "Apa URL endpoint persis untuk self-service password reset Active Directory?"
    row = candidate(
        "Use https://it.example.local/ad/reset for Active Directory password reset.",
        score=0.80,
        evidence_score=0.90,
        supported=True,
        exact=0.70,
    )
    # Simulate a cross-encoder lifting a weak baseline candidate above the final
    # threshold. The separate base-score floor must still reject it.
    row["baseScore"] = 0.18
    row["rerankerApplied"] = True
    row["rerankerScore"] = 1.0
    decision = assess_answerability(question, [row])
    assert not decision.answerable
    assert "minimum_base_hybrid_score" in decision.failed_checks


def test_supported_candidate_with_sufficient_base_score_still_passes() -> None:
    question = "Bagaimana prosedur reset password dan berapa lama prosesnya?"
    row = candidate(
        "Raise a ticket to the IT Helpdesk portal. Password resets are processed within 1x24 hours.",
        score=0.72,
        evidence_score=0.85,
        supported=True,
        exact=0.45,
    )
    row["baseScore"] = 0.52
    row["rerankerApplied"] = True
    row["rerankerScore"] = 0.90
    decision = assess_answerability(question, [row])
    assert decision.answerable, decision

def test_low_score_is_rejected() -> None:
    question = "Apa kebijakan kerja dari rumah?"
    rows = [candidate("Work from home is available with manager approval.", score=0.25)]
    decision = assess_answerability(question, rows)
    assert not decision.answerable
    assert "minimum_top_score" in decision.failed_checks


if __name__ == "__main__":
    tests = [
        test_regular_answerable_password_question_passes,
        test_exact_url_question_is_rejected_without_literal_url,
        test_exact_url_question_passes_with_literal_url,
        test_paternity_question_does_not_accept_maternity_policy,
        test_frequency_question_requires_explicit_cadence,
        test_monetary_threshold_requires_currency_amount,
        test_explicit_numeric_constraints_must_be_in_evidence,
        test_compliance_scenario_uses_policy_threshold_not_literal_value,
        test_compliance_percentage_can_be_compared_with_different_threshold,
        test_high_reranker_score_cannot_rescue_weak_hybrid_candidate,
        test_supported_candidate_with_sufficient_base_score_still_passes,
        test_low_score_is_rejected,
    ]
    for test in tests:
        test()
    print("Answerability gate tests passed.")
