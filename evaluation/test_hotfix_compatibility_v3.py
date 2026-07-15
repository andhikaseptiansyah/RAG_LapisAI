from __future__ import annotations

from api.grounding_validator import validate_grounded_answer
from retrieval.answerability import assess_answerability


def row(chunk_id: str, content: str, *, score: float = 0.76, evidence: float = 0.9) -> dict:
    return {
        "chunkId": chunk_id,
        "content": content,
        "score": score,
        "baseScore": score,
        "preEvidenceScore": score,
        "evidenceScore": evidence,
        "evidenceSupported": True,
        "exactTokenCoverage": 0.35,
        "documentName": f"{chunk_id}.pdf",
        "metadata": {"filename": f"{chunk_id}.pdf", "page": 1},
    }


def chunks(content: str) -> list[dict]:
    item = row("source", content, score=0.9)
    item["answerabilityAccepted"] = True
    item["answerabilityEvidenceSelected"] = True
    item["contextSelected"] = True
    return [item]


def test_second_ranked_exact_evidence_can_make_bundle_answerable() -> None:
    question = "Berapa batas waktu pengajuan klaim biaya?"
    rows = [
        row("generic", "The expense policy explains eligible business expenses.", score=0.76),
        row("deadline", "Expense claims must be submitted within 30 days of the expense date.", score=0.70),
    ]
    decision = assess_answerability(question, rows)
    assert decision.answerable, decision
    assert "deadline" in decision.evidence_chunk_ids


def test_multi_document_amount_and_receipt_requirements_pass() -> None:
    question = "Berapa tunjangan home-office dan bukti apa yang harus disertakan untuk reimbursement?"
    rows = [
        row("allowance", "Employees receive a one-time home-office allowance of IDR 1,500,000.", score=0.78),
        row("receipt", "Reimbursement requests must include the original receipt and proof of payment.", score=0.68),
    ]
    decision = assess_answerability(question, rows)
    assert decision.answerable, decision
    assert decision.requirement_coverage == 1.0


def test_plural_data_breach_alias_is_supported() -> None:
    decision = assess_answerability(
        "Who must a suspected data breach be reported to and how fast?",
        [row("security", "Suspected data breaches must be reported to security@example.com within 1 hour.", score=0.84)],
    )
    assert decision.answerable is True
    assert "concept:data_breach" in decision.passed_checks


def test_paternity_question_does_not_accept_maternity_policy() -> None:
    decision = assess_answerability(
        "Berapa hari paternity leave untuk karyawan pria ketika pasangannya melahirkan?",
        [row("leave", "Female employees receive paid maternity leave after childbirth.")],
    )
    assert not decision.answerable
    assert "missing_concept:paternity_leave" in decision.failed_checks


def test_missing_requested_percentage_is_rejected() -> None:
    result = validate_grounded_answer(
        "Berapa pendapatan FY2025 dan margin laba bersihnya?",
        "Pendapatan FY2025 adalah IDR 158 miliar.",
        chunks("Full-year 2025 revenue was IDR 158 billion, with a 14% net profit margin."),
    )
    assert not result.supported


def test_same_number_with_wrong_unit_is_rejected() -> None:
    result = validate_grounded_answer(
        "Berapa lama penyimpanan log?",
        "Log disimpan selama 50 hari.",
        chunks("The standard mailbox quota is 50 GB."),
    )
    assert not result.supported
    assert any("50 days" in fact for fact in result.unsupported_facts)


def test_multi_separator_currency_amount_is_checked_as_one_fact() -> None:
    result = validate_grounded_answer(
        "Berapa tunjangan home-office?",
        "Tunjangan home-office adalah IDR 2,000,000.",
        chunks("Employees receive a one-time home-office allowance of IDR 1,500,000."),
    )
    assert not result.supported
    assert "idr 2000000" in result.unsupported_facts
