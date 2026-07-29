"""Strict post-rerank answerability gate for evidence bundles.

Similarity is not proof. This module rejects a query unless the selected
retrieval bundle contains the requested subject, answer type, and constraints.
For a single-fact question, those elements must normally co-occur in at least
one chunk so unrelated documents cannot be stitched into a false answer.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from retrieval.evidence_verifier import HARD_CONCEPTS, _concept_match
from retrieval.query_expansion import concepts_in_text
from retrieval.requirements import (
    EvidenceRequirement,
    evaluate_requirements,
    extract_evidence_requirements,
    requirement_satisfied,
)
from uploads.config import (
    ANSWERABILITY_MAX_CONTEXTS,
    ANSWERABILITY_MIN_BASE_SCORE,
    ANSWERABILITY_MIN_EVIDENCE_SCORE,
    ANSWERABILITY_MIN_SCORE_MARGIN,
    ANSWERABILITY_MIN_TOP_SCORE,
    ANSWERABILITY_REQUIRE_COHERENT_EVIDENCE,
    ANSWERABILITY_REQUIRE_SUPPORTED_EVIDENCE,
    ANSWERABILITY_STRONG_EXACT_COVERAGE,
    ANSWERABILITY_STRONG_RETRIEVAL_SCORE,
)


@dataclass(frozen=True)
class AnswerabilityDecision:
    answerable: bool
    score: float
    reason: str
    failed_checks: tuple[str, ...]
    passed_checks: tuple[str, ...]
    top_score: float
    top_base_score: float
    top_evidence_score: float
    top_exact_coverage: float
    score_margin: float
    supporting_candidate_count: int
    precision_requirement_count: int
    requirement_coverage: float = 0.0
    concept_coverage: float = 0.0
    evidence_chunk_ids: tuple[str, ...] = ()
    coherent_candidate_count: int = 0
    coherent_chunk_ids: tuple[str, ...] = ()
    requires_coherent_evidence: bool = False
    strictly_supported: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["failed_checks"] = list(self.failed_checks)
        payload["passed_checks"] = list(self.passed_checks)
        payload["evidence_chunk_ids"] = list(self.evidence_chunk_ids)
        payload["coherent_chunk_ids"] = list(self.coherent_chunk_ids)
        return payload


def _clamp(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(score, 1.0))


def _base_score(candidate: dict[str, Any]) -> float:
    value = candidate.get("baseScore")
    if value is None:
        value = candidate.get("preEvidenceScore", candidate.get("score"))
    return _clamp(value)


def _legacy_requirement_name(key: str) -> str:
    mapping = {
        "answer_url": "explicit_url_or_endpoint",
        "answer_version": "explicit_version_value",
        "answer_cadence": "explicit_frequency",
        "answer_money": "explicit_monetary_value",
        "answer_percentage": "explicit_percentage",
        "answer_storage": "explicit_storage_quantity",
        "answer_duration": "explicit_duration",
        "answer_date_or_time": "explicit_date_or_time",
        "answer_count": "explicit_count",
        "answer_approval": "explicit_approval",
        "answer_contact": "explicit_reporting_contact",
        "answer_supporting_document": "explicit_supporting_document",
    }
    if key.startswith("quoted:"):
        return "quoted_phrase:" + key.split(":", 1)[1]
    if key.startswith("constraint:"):
        _, number, unit = key.split(":", 2)
        return f"explicit_constraint:{number}_{unit}"
    return mapping.get(key, key)


def _candidate_location(candidate: dict[str, Any]) -> tuple[str, str, str]:
    metadata = candidate.get("metadata") or {}
    return (
        str(candidate.get("documentName") or metadata.get("filename") or "").casefold(),
        str(candidate.get("page", metadata.get("page")) or ""),
        str(metadata.get("paragraph_start") or candidate.get("paragraphStart") or ""),
    )


def _select_evidence_candidates(
    ranked: list[dict[str, Any]],
    max_contexts: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_chunks: set[str] = set()
    seen_locations: set[tuple[str, str, str]] = set()

    for candidate in ranked:
        if candidate.get("evidenceHardFailures"):
            continue
        if candidate.get("evidenceHardContradictions"):
            continue
        content = str(candidate.get("content") or "").strip()
        if not content:
            continue

        chunk_id = str(candidate.get("chunkId") or "")
        location = _candidate_location(candidate)
        if chunk_id and chunk_id in seen_chunks:
            continue
        if location[0] and location in seen_locations:
            continue

        selected.append(candidate)
        if chunk_id:
            seen_chunks.add(chunk_id)
        seen_locations.add(location)
        if len(selected) >= max(1, int(max_contexts)):
            break

    return selected


def _bundle_concepts(
    question: str,
    evidence_texts: list[str],
) -> tuple[set[str], set[str]]:
    required = set(concepts_in_text(question)).intersection(HARD_CONCEPTS)
    present = {
        concept
        for concept in required
        if any(_concept_match(concept, text) for text in evidence_texts)
    }
    return required, present


def _is_multi_part_question(question: str, requirements: list[EvidenceRequirement]) -> bool:
    normalized = re.sub(r"\s+", " ", str(question or "").casefold()).strip()
    conjunction = bool(re.search(r"\b(?:and|dan|serta|beserta|as well as)\b", normalized))
    multiple_question_marks = str(question or "").count("?") > 1
    # Multiple explicit answer types normally indicate a composite request even
    # when the user omits a conjunction.
    multiple_answer_types = len([item for item in requirements if item.key.startswith("answer_")]) > 1
    return conjunction or multiple_question_marks or multiple_answer_types


def _candidate_satisfies_all(
    candidate: dict[str, Any],
    required_concepts: set[str],
    requirements: list[EvidenceRequirement],
) -> bool:
    text = str(candidate.get("content") or "")
    if not text or candidate.get("evidenceHardContradictions"):
        return False
    if any(not _concept_match(concept, text) for concept in required_concepts):
        return False
    if any(not requirement_satisfied(requirement, [text]) for requirement in requirements):
        return False
    return True


def assess_answerability(
    question: str,
    candidates: list[dict[str, Any]],
    *,
    min_top_score: float = ANSWERABILITY_MIN_TOP_SCORE,
    min_base_score: float = ANSWERABILITY_MIN_BASE_SCORE,
    min_evidence_score: float = ANSWERABILITY_MIN_EVIDENCE_SCORE,
    min_score_margin: float = ANSWERABILITY_MIN_SCORE_MARGIN,
    require_supported_evidence: bool = ANSWERABILITY_REQUIRE_SUPPORTED_EVIDENCE,
    max_contexts: int = ANSWERABILITY_MAX_CONTEXTS,
) -> AnswerabilityDecision:
    if not candidates:
        return AnswerabilityDecision(
            answerable=False,
            score=0.0,
            reason="No retrieval candidate survived filtering.",
            failed_checks=("no_candidates",),
            passed_checks=(),
            top_score=0.0,
            top_base_score=0.0,
            top_evidence_score=0.0,
            top_exact_coverage=0.0,
            score_margin=0.0,
            supporting_candidate_count=0,
            precision_requirement_count=0,
        )

    ranked = sorted(candidates, key=lambda row: _clamp(row.get("score")), reverse=True)
    selected = _select_evidence_candidates(ranked, max_contexts=max_contexts)
    if not selected:
        return AnswerabilityDecision(
            answerable=False,
            score=0.0,
            reason="All retrieval candidates contain contradictions or empty evidence.",
            failed_checks=("no_noncontradictory_evidence",),
            passed_checks=(),
            top_score=0.0,
            top_base_score=0.0,
            top_evidence_score=0.0,
            top_exact_coverage=0.0,
            score_margin=0.0,
            supporting_candidate_count=0,
            precision_requirement_count=0,
        )

    top = selected[0]
    top_score = _clamp(top.get("score"))
    strongest_base_score = max((_base_score(item) for item in selected), default=0.0)
    top_evidence_score = _clamp(top.get("evidenceScore"))
    top_exact_coverage = _clamp(top.get("exactTokenCoverage"))
    second_score = _clamp(selected[1].get("score")) if len(selected) > 1 else 0.0
    score_margin = max(0.0, top_score - second_score)

    evidence_texts = [str(candidate.get("content") or "") for candidate in selected]
    requirement_passed_raw, requirement_failed_raw, requirements = evaluate_requirements(
        question,
        evidence_texts,
    )
    requirement_passed = [_legacy_requirement_name(key) for key in requirement_passed_raw]
    requirement_failed = [_legacy_requirement_name(key) for key in requirement_failed_raw]
    requirement_coverage = len(requirement_passed_raw) / len(requirements) if requirements else 1.0

    required_concepts, present_concepts = _bundle_concepts(question, evidence_texts)
    missing_concepts = required_concepts - present_concepts
    concept_coverage = len(present_concepts) / len(required_concepts) if required_concepts else 1.0

    has_semantic_requirements = bool(requirements or required_concepts)
    multi_part = _is_multi_part_question(question, requirements)
    requires_coherent_evidence = bool(
        ANSWERABILITY_REQUIRE_COHERENT_EVIDENCE
        and has_semantic_requirements
        and not multi_part
    )

    coherent = [
        candidate
        for candidate in selected
        if _candidate_satisfies_all(candidate, required_concepts, requirements)
    ]
    coherent_chunk_ids = tuple(
        str(item.get("chunkId") or "")
        for item in coherent
        if item.get("chunkId")
    )

    supporting = [
        candidate
        for candidate in selected
        if candidate.get("evidenceSupported") is True
        and not candidate.get("evidenceContradictions")
        and not candidate.get("evidenceHardContradictions")
        and _clamp(candidate.get("evidenceScore")) >= min_evidence_score
    ]
    supporting_candidate_count = len(supporting)

    passed: list[str] = list(requirement_passed)
    failed: list[str] = list(requirement_failed)

    for concept in sorted(present_concepts):
        passed.append(f"concept:{concept}")
    for concept in sorted(missing_concepts):
        failed.append(f"missing_concept:{concept}")
        if concept == "paternity_leave":
            failed.append("paternity_leave_subject")

    coverage_complete = requirement_coverage >= 1.0 and concept_coverage >= 1.0
    coherent_complete = bool(coherent) or not requires_coherent_evidence
    evidence_supported = supporting_candidate_count > 0
    strictly_supported = coverage_complete and coherent_complete and evidence_supported

    strongest_exact_coverage = max(
        (_clamp(candidate.get("exactTokenCoverage")) for candidate in selected),
        default=0.0,
    )
    strong_bundle_fallback = (
        not has_semantic_requirements
        and top_score >= ANSWERABILITY_STRONG_RETRIEVAL_SCORE
        and strongest_base_score >= min_base_score
        and strongest_exact_coverage >= ANSWERABILITY_STRONG_EXACT_COVERAGE
    )

    # Verified evidence may override low display scores only when no reranker was
    # used. A cross-encoder must never resurrect a weak base retrieval result.
    reranker_applied = any(bool(item.get("rerankerApplied")) for item in selected)
    strong_evidence_override = strictly_supported and has_semantic_requirements and not reranker_applied

    if top_score >= min_top_score:
        passed.append("minimum_top_score")
    elif strong_evidence_override:
        passed.append("minimum_top_score_overridden_by_verified_evidence")
    else:
        failed.append("minimum_top_score")

    if strongest_base_score >= min_base_score:
        passed.append("minimum_base_hybrid_score")
    elif strong_evidence_override:
        passed.append("minimum_base_score_overridden_by_verified_evidence")
    else:
        failed.append("minimum_base_hybrid_score")

    if evidence_supported:
        passed.append("supported_evidence")
    elif strong_bundle_fallback:
        passed.append("strong_retrieval_fallback")
    elif require_supported_evidence or has_semantic_requirements:
        failed.append("supported_evidence")

    if requires_coherent_evidence:
        if coherent:
            passed.append("coherent_single_chunk_evidence")
        else:
            failed.append("no_coherent_single_chunk_evidence")
    else:
        passed.append("bundle_coherence_allowed")

    ambiguous_ranking = (
        min_score_margin > 0
        and len(selected) > 1
        and score_margin < min_score_margin
        and not strictly_supported
        and top_score < ANSWERABILITY_STRONG_RETRIEVAL_SCORE
    )
    if ambiguous_ranking:
        failed.append("ambiguous_top_margin")
    else:
        passed.append("top_margin_or_bundle_support")

    support_signal = min(supporting_candidate_count / 2.0, 1.0)
    mean_evidence = sum(_clamp(item.get("evidenceScore")) for item in selected) / len(selected)
    coherence_signal = 1.0 if coherent_complete else 0.0
    answerability_score = _clamp(
        0.24 * top_score
        + 0.16 * strongest_base_score
        + 0.18 * mean_evidence
        + 0.17 * requirement_coverage
        + 0.13 * concept_coverage
        + 0.07 * support_signal
        + 0.05 * coherence_signal
    )

    unique_failed = tuple(dict.fromkeys(failed))
    unique_passed = tuple(dict.fromkeys(passed))
    answerable = not unique_failed
    strictly_supported = bool(answerable and (evidence_supported or strong_bundle_fallback))
    reason = (
        "The evidence bundle satisfies the requested subject, answer type, and constraints."
        if answerable
        else "Retrieval rejected: " + ", ".join(unique_failed)
    )

    evidence_chunk_ids = tuple(
        str(item.get("chunkId") or "")
        for item in selected
        if item.get("chunkId")
    )

    return AnswerabilityDecision(
        answerable=answerable,
        score=round(answerability_score, 6),
        reason=reason,
        failed_checks=unique_failed,
        passed_checks=unique_passed,
        top_score=round(top_score, 6),
        top_base_score=round(strongest_base_score, 6),
        top_evidence_score=round(top_evidence_score, 6),
        top_exact_coverage=round(top_exact_coverage, 6),
        score_margin=round(score_margin, 6),
        supporting_candidate_count=supporting_candidate_count,
        precision_requirement_count=len(requirements),
        requirement_coverage=round(requirement_coverage, 6),
        concept_coverage=round(concept_coverage, 6),
        evidence_chunk_ids=evidence_chunk_ids,
        coherent_candidate_count=len(coherent),
        coherent_chunk_ids=coherent_chunk_ids,
        requires_coherent_evidence=requires_coherent_evidence,
        strictly_supported=strictly_supported,
    )


def apply_answerability_gate(
    question: str,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    decision = assess_answerability(question, candidates)
    if not decision.answerable:
        print(f"[ANSWERABILITY] Rejected query: {decision.reason}")
        return []

    metadata = decision.to_dict()
    selected_ids = set(decision.evidence_chunk_ids)
    coherent_ids = set(decision.coherent_chunk_ids)
    return [
        {
            **candidate,
            "answerabilityAccepted": True,
            "answerabilityStrictlySupported": decision.strictly_supported,
            "answerabilityScore": decision.score,
            "answerabilityReason": decision.reason,
            "answerabilityScoreMargin": decision.score_margin,
            "answerabilitySupportingCandidates": decision.supporting_candidate_count,
            "answerabilityPrecisionRequirementCount": decision.precision_requirement_count,
            "answerabilityRequirementCoverage": decision.requirement_coverage,
            "answerabilityConceptCoverage": decision.concept_coverage,
            "answerabilityRequiresCoherentEvidence": decision.requires_coherent_evidence,
            "answerabilityCoherentEvidence": (
                not decision.requires_coherent_evidence
                or str(candidate.get("chunkId") or "") in coherent_ids
            ),
            "answerabilityEvidenceSelected": (
                not selected_ids or str(candidate.get("chunkId") or "") in selected_ids
            ),
            "answerabilityDiagnostics": metadata,
        }
        for candidate in candidates
    ]
