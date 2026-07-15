"""Post-rerank answerability gate for top-k evidence bundles.

The gate evaluates the complete evidence bundle. A lower-ranked chunk may satisfy
an explicit requirement that is missing from the first result, and multi-part
questions may be supported by complementary documents. Diagnostics remain stable
for the API and regression tests.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from retrieval.evidence_verifier import HARD_CONCEPTS, _concept_match
from retrieval.query_expansion import concepts_in_text
from retrieval.requirements import evaluate_requirements
from uploads.config import (
    ANSWERABILITY_MAX_CONTEXTS,
    ANSWERABILITY_MIN_BASE_SCORE,
    ANSWERABILITY_MIN_EVIDENCE_SCORE,
    ANSWERABILITY_MIN_SCORE_MARGIN,
    ANSWERABILITY_MIN_TOP_SCORE,
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

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["failed_checks"] = list(self.failed_checks)
        payload["passed_checks"] = list(self.passed_checks)
        payload["evidence_chunk_ids"] = list(self.evidence_chunk_ids)
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
    """Map generic requirements to stable diagnostic labels."""
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
    """Keep diverse, non-empty, non-contradictory evidence candidates."""
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

    supporting = [
        candidate
        for candidate in selected
        if not candidate.get("evidenceContradictions")
        and not candidate.get("evidenceHardContradictions")
        and (
            candidate.get("evidenceSupported") is True
            or _clamp(candidate.get("evidenceScore")) >= min_evidence_score
            or _clamp(candidate.get("score")) >= ANSWERABILITY_STRONG_RETRIEVAL_SCORE
        )
    ]
    supporting_candidate_count = len(supporting)

    # Requirements and concepts are evaluated against the complete selected
    # bundle. This is what allows a second-ranked or second-document chunk to
    # complete an otherwise partial answer.
    evidence_texts = [str(candidate.get("content") or "") for candidate in selected]
    requirement_passed_raw, requirement_failed_raw, requirements = evaluate_requirements(
        question,
        evidence_texts,
    )
    requirement_passed = [_legacy_requirement_name(key) for key in requirement_passed_raw]
    requirement_failed = [_legacy_requirement_name(key) for key in requirement_failed_raw]
    requirement_coverage = (
        len(requirement_passed_raw) / len(requirements)
        if requirements
        else 1.0
    )

    required_concepts, present_concepts = _bundle_concepts(question, evidence_texts)
    missing_concepts = required_concepts - present_concepts
    concept_coverage = (
        len(present_concepts) / len(required_concepts)
        if required_concepts
        else 1.0
    )

    passed: list[str] = list(requirement_passed)
    failed: list[str] = list(requirement_failed)

    for concept in sorted(present_concepts):
        passed.append(f"concept:{concept}")
    for concept in sorted(missing_concepts):
        failed.append(f"missing_concept:{concept}")
        # Preserve the older UI/test diagnostic while retaining the generic label.
        if concept == "paternity_leave":
            failed.append("paternity_leave_subject")

    strongest_exact_coverage = max(
        (_clamp(candidate.get("exactTokenCoverage")) for candidate in selected),
        default=0.0,
    )
    strong_bundle_fallback = (
        top_score >= ANSWERABILITY_STRONG_RETRIEVAL_SCORE
        and strongest_base_score >= min_base_score
        and (
            strongest_exact_coverage >= ANSWERABILITY_STRONG_EXACT_COVERAGE
            or requirement_coverage >= 1.0
        )
    )
    evidence_supported = supporting_candidate_count > 0 or strong_bundle_fallback
    has_semantic_requirements = bool(requirements or required_concepts)
    coverage_complete = requirement_coverage >= 1.0 and concept_coverage >= 1.0
    # Explicit and fully covered requirements may override low display scores
    # when the candidate has not been lifted by a reranker. Once reranking is
    # applied, the original hybrid/base-score floor remains a hard veto so a
    # cross-encoder cannot resurrect a weak retrieval result. Generic topical
    # similarity never receives this override.
    strong_evidence_override = (
        evidence_supported
        and has_semantic_requirements
        and coverage_complete
        and (
            supporting_candidate_count > 0
            or top_evidence_score >= max(min_evidence_score, 0.55)
            or strongest_exact_coverage >= 0.45
        )
    )
    reranker_applied = any(bool(item.get("rerankerApplied")) for item in selected)
    base_score_override = strong_evidence_override and not reranker_applied

    if top_score >= min_top_score:
        passed.append("minimum_top_score")
    elif strong_evidence_override:
        passed.append("minimum_top_score_overridden_by_verified_evidence")
    else:
        failed.append("minimum_top_score")

    if strongest_base_score >= min_base_score:
        passed.append("minimum_base_hybrid_score")
    elif base_score_override:
        passed.append("minimum_base_score_overridden_by_verified_evidence")
    else:
        failed.append("minimum_base_hybrid_score")

    if supporting_candidate_count > 0:
        passed.append("supported_evidence")
    elif strong_bundle_fallback:
        passed.append("strong_retrieval_fallback")
    elif require_supported_evidence:
        failed.append("supported_evidence")

    ambiguous_ranking = (
        min_score_margin > 0
        and len(selected) > 1
        and score_margin < min_score_margin
        and not evidence_supported
        and top_score < ANSWERABILITY_STRONG_RETRIEVAL_SCORE
        and requirement_coverage < 1.0
    )
    if ambiguous_ranking and not strong_evidence_override:
        failed.append("ambiguous_top_margin")
    else:
        passed.append("top_margin_or_bundle_support")

    support_signal = min(supporting_candidate_count / 2.0, 1.0)
    mean_evidence = sum(_clamp(item.get("evidenceScore")) for item in selected) / len(selected)
    answerability_score = _clamp(
        0.28 * top_score
        + 0.17 * strongest_base_score
        + 0.18 * mean_evidence
        + 0.17 * requirement_coverage
        + 0.12 * concept_coverage
        + 0.08 * support_signal
    )

    unique_failed = tuple(dict.fromkeys(failed))
    unique_passed = tuple(dict.fromkeys(passed))
    answerable = not unique_failed
    reason = (
        "Top-k evidence collectively satisfies the question without contradictions."
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
    return [
        {
            **candidate,
            "answerabilityAccepted": True,
            "answerabilityScore": decision.score,
            "answerabilityReason": decision.reason,
            "answerabilityScoreMargin": decision.score_margin,
            "answerabilitySupportingCandidates": decision.supporting_candidate_count,
            "answerabilityPrecisionRequirementCount": decision.precision_requirement_count,
            "answerabilityRequirementCoverage": decision.requirement_coverage,
            "answerabilityConceptCoverage": decision.concept_coverage,
            "answerabilityEvidenceSelected": (
                not selected_ids or str(candidate.get("chunkId") or "") in selected_ids
            ),
            "answerabilityDiagnostics": metadata,
        }
        for candidate in candidates
    ]
