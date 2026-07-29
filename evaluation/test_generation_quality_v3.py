from __future__ import annotations

from api.answer_formatter import (
    build_safe_extractive_answer,
    build_sources,
    has_answerable_evidence,
    top_confidence,
)
from api.grounding_validator import validate_grounded_answer
from api.ollama_client import _is_likely_incomplete_answer
from retrieval.answerability import assess_answerability
from retrieval.requirements import extract_evidence_requirements


def row(
    chunk_id: str,
    content: str,
    *,
    score: float = 0.2,
    base: float = 0.1,
    evidence: float = 0.9,
    exact: float = 0.5,
    document: str = "policy.pdf",
) -> dict:
    return {
        "chunkId": chunk_id,
        "content": content,
        "score": score,
        "baseScore": base,
        "evidenceScore": evidence,
        "evidenceSupported": True,
        "exactTokenCoverage": exact,
        "documentName": document,
        "metadata": {"filename": document, "page": 1},
    }


def accepted_row(chunk_id: str, content: str, *, score: float = 0.2) -> dict:
    item = row(chunk_id, content, score=score)
    item.update(
        {
            "answerabilityAccepted": True,
            "answerabilityEvidenceSelected": True,
            "answerabilityScore": 0.72,
            "answerabilityRequirementCoverage": 1.0,
            "answerabilityConceptCoverage": 1.0,
            "contextSelected": True,
        }
    )
    return item


def test_verified_requirement_coverage_can_override_low_display_scores() -> None:
    decision = assess_answerability(
        "How long is the probation period?",
        [row("probation", "The probation period is three months.")],
    )
    assert decision.answerable is True
    assert "minimum_top_score_overridden_by_verified_evidence" in decision.passed_checks
    assert "minimum_base_score_overridden_by_verified_evidence" in decision.passed_checks


def test_answerability_acceptance_is_not_rejected_by_ui_confidence() -> None:
    chunks = [accepted_row("mailbox", "The mailbox size limit is 50 GB.", score=0.05)]
    assert has_answerable_evidence(chunks)
    assert top_confidence(chunks, question="What is the mailbox size limit?") > 0
    assert build_sources(chunks, question="What is the mailbox size limit?")


def test_short_complete_answers_are_not_marked_incomplete() -> None:
    assert not _is_likely_incomplete_answer(
        "What database does the platform use?",
        "PostgreSQL.",
    )
    assert not _is_likely_incomplete_answer(
        "What is the mailbox size limit?",
        "50 GB.",
    )


def test_safe_fallback_returns_direct_evidence_not_question_text() -> None:
    chunks = [
        accepted_row(
            "faq",
            "Q: What is the mailbox size limit? A: The mailbox size limit is 50 GB.",
        )
    ]
    answer = build_safe_extractive_answer(
        "What is the mailbox size limit?",
        chunks,
        language="EN",
    )
    assert "50 GB" in answer
    assert not answer.startswith("Q:")
    assert "What is the mailbox" not in answer


def test_grounding_rejects_short_unsupported_technology() -> None:
    result = validate_grounded_answer(
        "What database does the platform use?",
        "MySQL.",
        [accepted_row("db", "The platform uses PostgreSQL as its primary database.")],
    )
    assert result.supported is False
    assert result.unsupported_claims


def test_grounding_rejects_cross_chunk_relation_swapping() -> None:
    chunks = [
        accepted_row("p1", "P1 incidents must be resolved within 4 hours."),
        accepted_row("p2", "P2 incidents must be acknowledged within 1 hour."),
    ]
    result = validate_grounded_answer(
        "How fast must a P1 incident be acknowledged?",
        "A P1 incident must be acknowledged within 1 hour.",
        chunks,
    )
    assert result.supported is False
    assert result.unsupported_claims


def test_official_numeric_answer_types_are_extracted() -> None:
    cases = {
        "What was Q3 2025 revenue?": "answer_money",
        "What was the 2025 overall CSAT score?": "answer_percentage",
        "What is the API availability SLO?": "answer_percentage",
        "What unit-test coverage is required to merge code?": "answer_percentage",
        "What is the mailbox size limit?": "answer_storage",
    }
    for question, expected in cases.items():
        keys = {item.key for item in extract_evidence_requirements(question)}
        assert expected in keys, (question, keys)
