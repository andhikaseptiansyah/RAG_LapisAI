"""Answerability gate for post-rerank, top-k evidence bundles.

The gate answers one question only: does the retrieved bundle contain explicit,
non-contradictory evidence for every precision-sensitive part of the question?
It does not contain benchmark-specific topic rules and it never relies on only
the first chunk when several documents are required.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from retrieval.evidence_verifier import HARD_CONCEPTS, concept_matches_text
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


def _legacy_requirement_key(key: str) -> str:
    mappings = {
        "answer_url": "explicit_url_or_endpoint",
        "answer_version": "explicit_version",
        "answer_cadence": "explicit_frequency",
        "answer_money": "explicit_monetary_value",
        "answer_percentage": "explicit_percentage",
        "answer_duration": "explicit_duration",
        "answer_date_or_time": "explicit_date_or_time",
        "answer_count": "explicit_numeric_count",
    }
    if key in mappings:
        return mappings[key]
    if key.startswith("quoted:"):
        return "quoted_phrase:" + key.split(":", 1)[1]
    if key.startswith("constraint:"):
        _, number, unit = key.split(":", 2)
        return f"explicit_constraint:{number}_{unit}"
    return key


def _select_evidence_candidates(
    ranked: list[dict[str, Any]],
    max_contexts: int,
) -> list[dict[str, Any]]:
    """Select diverse, non-contradictory contexts for bundle-level validation."""
    selected: list[dict[str, Any]] = []
    seen_chunks: set[str] = set()
    seen_locations: set[tuple[str, str, str]] = set()

    for candidate in ranked:
        if candidate.get("evidenceHardFailures"):
            continue
        content = str(candidate.get("content") or "").strip()
        if not content:
            continue

        metadata = candidate.get("metadata") or {}
        chunk_id = str(candidate.get("chunkId") or "")
        location = (
            str(candidate.get("documentName") or metadata.get("filename") or "").casefold(),
            str(candidate.get("page", metadata.get("page")) or ""),
            str(metadata.get("paragraph_start") or candidate.get("paragraphStart") or ""),
        )
        if chunk_id and chunk_id in seen_chunks:
            continue
        if location in seen_locations and location[0]:
            continue

        selected.append(candidate)
        if chunk_id:
            seen_chunks.add(chunk_id)
        seen_locations.add(location)
        if len(selected) >= max(int(max_contexts), 1):
            break

    return selected


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
    """Assess the complete top-k evidence bundle, not only the first chunk."""
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

    supporting_candidate_count = sum(
        1
        for candidate in selected
        if candidate.get("evidenceSupported") is True
        and _clamp(candidate.get("evidenceScore")) >= min_evidence_score
    )

    evidence_texts = [str(candidate.get("content") or "") for candidate in selected]
    requirement_passed_raw, requirement_failed_raw, requirements = evaluate_requirements(
        question,
        evidence_texts,
    )
    requirement_passed = [_legacy_requirement_key(key) for key in requirement_passed_raw]
    requirement_failed = [_legacy_requirement_key(key) for key in requirement_failed_raw]
    requirement_coverage = (
        len(requirement_passed_raw) / len(requirements)
        if requirements
        else 1.0
    )

    required_concepts = set(concepts_in_text(question)).intersection(HARD_CONCEPTS)
    combined_evidence = "\n".join(evidence_texts)
    matched_concepts = {
        concept for concept in required_concepts
        if concept_matches_text(concept, combined_evidence)
    }
    missing_concepts = required_concepts - matched_concepts
    concept_coverage = (
        len(matched_concepts) / len(required_concepts)
        if required_concepts
        else 1.0
    )

    passed: list[str] = list(requirement_passed)
    failed: list[str] = list(requirement_failed)

    for concept in sorted(matched_concepts):
        passed.append(f"concept:{concept}")
    for concept in sorted(missing_concepts):
        failed.append(f"missing_concept:{concept}")

    if top_score >= min_top_score:
        passed.append("minimum_top_score")
    else:
        failed.append("minimum_top_score")

    # Reranking may promote a relevant passage, but at least one selected chunk
    # must still have non-trivial support from the original hybrid retriever.
    if strongest_base_score >= min_base_score:
        passed.append("minimum_base_hybrid_score")
    else:
        failed.append("minimum_base_hybrid_score")

    strong_bundle_fallback = (
        top_score >= ANSWERABILITY_STRONG_RETRIEVAL_SCORE
        and strongest_base_score >= min_base_score
        and (
            top_exact_coverage >= ANSWERABILITY_STRONG_EXACT_COVERAGE
            or requirement_coverage >= 1.0
        )
    )
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
        and supporting_candidate_count == 0
        and top_score < ANSWERABILITY_STRONG_RETRIEVAL_SCORE
        and requirement_coverage < 1.0
    )
    if ambiguous_ranking:
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
    if answerable:
        reason = "Top-k evidence collectively satisfies the question without contradictions."
    else:
        reason = "Retrieval rejected: " + ", ".join(unique_failed)

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
        evidence_chunk_ids=tuple(
            str(item.get("chunkId") or "") for item in selected if item.get("chunkId")
        ),
    )


def apply_answerability_gate(
    question: str,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Annotate accepted candidates, or return an empty list when unsupported."""
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
