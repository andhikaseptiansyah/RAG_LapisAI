from __future__ import annotations

from api.grounding_validator import validate_grounded_answer
from retrieval.answerability import assess_answerability
from retrieval.context_selector import select_context_bundle


def row(content: str, score: float, document: str = "doc.txt") -> dict:
    return {
        "chunkId": f"{document}-{score}-{len(content)}",
        "documentName": document,
        "page": 1,
        "content": content,
        "score": score,
        "baseScore": score,
        "semanticScore": score,
        "keywordScore": score,
        "exactTokenCoverage": 0.45,
        "evidenceScore": 0.82,
        "evidenceSupported": True,
        "evidenceHardFailures": [],
        "evidenceContradictions": [],
        "metadata": {"filename": document, "page": 1},
    }


def test_selector_keeps_only_complete_evidence() -> None:
    question = "How long is the probation period for new employees?"
    selected = select_context_bundle(
        question,
        [
            row("General onboarding information for employees.", 0.94, "general.txt"),
            row("The probation period for new employees is three months.", 0.90, "SOP_Onboarding.pdf"),
            row("The probation period for new employees is three months.", 0.88, "SOP_Onboarding.pdf"),
        ],
        max_contexts=3,
    )
    assert len(selected) == 1
    assert selected[0]["documentName"] == "SOP_Onboarding.pdf"
    assert "answer_duration" in selected[0]["contextRequirementCoverage"]


def test_selector_combines_only_complementary_sources() -> None:
    question = "What is the maximum reimbursement and how long do employees have to submit it?"
    selected = select_context_bundle(
        question,
        [
            row("The maximum reimbursement is IDR 1,500,000.", 0.91, "Policy_Remote_Work.docx"),
            row("Claims must be submitted within 30 days.", 0.88, "SOP_Reimbursement.pdf"),
            row("The company reimburses eligible employee expenses.", 0.86, "FAQ_Expense.txt"),
        ],
        max_contexts=3,
    )
    assert len(selected) == 2
    assert {item["documentName"] for item in selected} == {
        "Policy_Remote_Work.docx",
        "SOP_Reimbursement.pdf",
    }


def test_answerability_uses_second_chunk_for_missing_requirement() -> None:
    question = "What exact URL is used for self-service password reset?"
    candidates = [
        row("Employees can contact the IT Helpdesk for password support.", 0.92, "FAQ_IT.txt"),
        row("Use https://it.example.local/reset for self-service password reset.", 0.87, "TECH_Identity.txt"),
    ]
    decision = assess_answerability(question, candidates)
    assert decision.answerable, decision
    assert "explicit_url_or_endpoint" in decision.passed_checks


def test_grounding_accepts_supported_paraphrase() -> None:
    chunks = [row("The probation period is three months. A performance review occurs in week 12.", 0.9)]
    decision = validate_grounded_answer(
        "How long is probation and when is the performance review?",
        "Probation lasts three months, and the performance review takes place in week 12.",
        chunks,
    )
    assert decision.supported, decision


def test_grounding_rejects_unsupported_amount_and_identifier() -> None:
    chunks = [row("The maximum reimbursement is IDR 1,500,000.", 0.9)]
    decision = validate_grounded_answer(
        "What is the maximum reimbursement?",
        "The maximum reimbursement is IDR 2,000,000 through system ZXQ9.",
        chunks,
    )
    assert not decision.supported
    assert "IDR 2,000,000" in decision.unsupported_facts
    assert "ZXQ9" in decision.unsupported_facts


def test_grounding_allows_indonesian_translation_of_english_evidence() -> None:
    chunks = [row("The probation period is three months.", 0.9)]
    decision = validate_grounded_answer(
        "Berapa lama masa probation karyawan baru?",
        "Masa probation karyawan baru berlangsung selama tiga bulan.",
        chunks,
    )
    assert decision.supported, decision


def test_selector_combines_amount_and_supporting_document_sources() -> None:
    question = "What is the reimbursement limit and what supporting document must be attached?"
    selected = select_context_bundle(
        question,
        [
            row("The reimbursement limit is IDR 1,500,000.", 0.93, "Policy_Remote_Work.docx"),
            row("The claim must include the original receipt.", 0.89, "SOP_Reimbursement.pdf"),
            row("Eligible employee expenses may be reimbursed.", 0.87, "FAQ_Expense.txt"),
        ],
        max_contexts=3,
    )
    assert len(selected) == 2
    assert {item["documentName"] for item in selected} == {
        "Policy_Remote_Work.docx",
        "SOP_Reimbursement.pdf",
    }


def test_answerability_requires_reporting_contact_and_duration() -> None:
    question = "Who must a suspected data breach be reported to and how fast?"
    decision = assess_answerability(
        question,
        [
            row(
                "Suspected data breaches must be reported to security@example.com within 1 hour.",
                0.92,
                "Policy_Data_Security.docx",
            )
        ],
    )
    assert decision.answerable, decision
    assert "explicit_reporting_contact" in decision.passed_checks
    assert "explicit_duration" in decision.passed_checks


def test_grounding_rejects_wrong_spelled_out_duration() -> None:
    chunks = [row("The probation period is three months.", 0.9)]
    decision = validate_grounded_answer(
        "How long is the probation period?",
        "The probation period is four months.",
        chunks,
    )
    assert not decision.supported
    assert "four months" in decision.unsupported_facts


def test_grounding_rejects_wrong_plain_count() -> None:
    chunks = [row("The company added 18 enterprise customers.", 0.9)]
    decision = validate_grounded_answer(
        "How many enterprise customers were added?",
        "The company added 19 enterprise customers.",
        chunks,
    )
    assert not decision.supported
    assert "19" in decision.unsupported_facts
