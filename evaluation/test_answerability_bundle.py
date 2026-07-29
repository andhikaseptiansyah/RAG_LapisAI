from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from retrieval.answerability import assess_answerability


def row(
    chunk_id: str,
    content: str,
    *,
    score: float = 0.70,
    base: float = 0.55,
    evidence: float = 0.72,
    supported: bool = True,
) -> dict:
    return {
        "chunkId": chunk_id,
        "documentName": f"{chunk_id}.txt",
        "content": content,
        "score": score,
        "baseScore": base,
        "semanticScore": base,
        "keywordScore": 0.45,
        "exactTokenCoverage": 0.35,
        "evidenceScore": evidence,
        "evidenceSupported": supported,
        "evidenceHardFailures": [],
    }


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
    question = (
        "Berapa tunjangan home-office dan bukti apa yang harus disertakan "
        "untuk reimbursement?"
    )
    rows = [
        row(
            "allowance",
            "Employees receive a one-time home-office allowance of IDR 1,500,000.",
            score=0.78,
        ),
        row(
            "receipt",
            "Reimbursement requests must include the original receipt and proof of payment.",
            score=0.68,
        ),
    ]
    decision = assess_answerability(question, rows)
    assert decision.answerable, decision
    assert decision.requirement_coverage == 1.0
    assert set(decision.evidence_chunk_ids) == {"allowance", "receipt"}


def test_multi_document_question_rejects_when_amount_missing() -> None:
    question = (
        "Berapa tunjangan home-office dan bukti apa yang harus disertakan "
        "untuk reimbursement?"
    )
    rows = [
        row(
            "receipt",
            "Reimbursement requests must include the original receipt and proof of payment.",
            score=0.76,
        )
    ]
    decision = assess_answerability(question, rows)
    assert not decision.answerable
    assert "explicit_monetary_value" in decision.failed_checks


def test_unanswerable_exact_url_still_rejects_related_portal_text() -> None:
    question = "Apa URL persis untuk reset password mandiri?"
    rows = [
        row(
            "portal",
            "Employees can request a password reset through the IT Helpdesk portal.",
            score=0.84,
            base=0.70,
            evidence=0.85,
        )
    ]
    decision = assess_answerability(question, rows)
    assert not decision.answerable
    assert "explicit_url_or_endpoint" in decision.failed_checks


def test_advance_notice_is_duration_not_money() -> None:
    chunks = [
        row(
            "leave",
            "Annual leave must be requested at least 5 working days in advance.",
            score=0.82,
            evidence=0.88,
        )
    ]
    decision = assess_answerability(
        "How much advance notice is required for annual leave?",
        chunks,
    )
    assert decision.answerable is True
    assert "explicit_duration" in decision.passed_checks
    assert "explicit_monetary_value" not in decision.failed_checks


def test_plural_data_breach_alias_is_supported() -> None:
    chunks = [
        row(
            "security",
            "Suspected data breaches must be reported to security@example.com within 1 hour.",
            score=0.84,
            evidence=0.90,
        )
    ]
    decision = assess_answerability(
        "Who must a suspected data breach be reported to and how fast?",
        chunks,
    )
    assert decision.answerable is True
    assert "concept:data_breach" in decision.passed_checks
