"""Cross-encoder reranking for hybrid retrieval candidates.

The reranker is a real second-stage ranker: it reads the query and every merged
semantic/BM25 candidate together and produces a relevance logit. The logit is
normalised per query and blended with the existing hybrid score.

Important: the cross-encoder is deliberately used as a *corrective signal*, not
as the only ordering signal. This avoids the failure mode observed in ablation
where an English-only reranker confidently displaced already-correct bilingual
hybrid results.

Model loading is lazy. If the optional model cannot be loaded, the original
hybrid order is preserved and retrieval continues safely.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any, Iterable

from retrieval.query_expansion import build_query_variants, requires_language_bridge
from uploads.config import ENABLE_RERANKER, RERANKER_MODEL, RERANKER_WEIGHT

_LOAD_ERROR_REPORTED = False


def _sigmoid(value: float) -> float:
    """Convert a logit to 0..1 as a stable fallback calibration."""
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _normalise_logits(values: Iterable[float]) -> list[float]:
    """Normalise cross-encoder logits within one query's candidate set.

    Cross-encoder logits are best interpreted relatively. Min-max normalisation
    keeps the ordering signal without treating raw logits as globally calibrated
    probabilities. If every logit is effectively identical, sigmoid is used so
    the reranker does not manufacture artificial differences.
    """
    safe_values = [float(value) for value in values]
    if not safe_values:
        return []

    minimum = min(safe_values)
    maximum = max(safe_values)
    spread = maximum - minimum
    if spread <= 1e-9:
        return [_sigmoid(value) for value in safe_values]

    return [max(0.0, min((value - minimum) / spread, 1.0)) for value in safe_values]


@lru_cache(maxsize=1)
def get_reranker():
    """Load the configured CrossEncoder only when reranking is first requested."""
    from sentence_transformers import CrossEncoder

    return CrossEncoder(RERANKER_MODEL)


def _report_load_error(exc: Exception) -> None:
    global _LOAD_ERROR_REPORTED
    if not _LOAD_ERROR_REPORTED:
        print(
            "[RERANKER] Cross-encoder unavailable; preserving hybrid order. "
            f"Reason: {exc}"
        )
        _LOAD_ERROR_REPORTED = True


def warmup_reranker() -> bool:
    if not ENABLE_RERANKER:
        return False

    try:
        model = get_reranker()
        model.predict(
            [[
                "Bagaimana prosedur reset password dan berapa lama prosesnya?",
                "Raise a ticket to the IT Helpdesk; resets are processed within 1x24 hours.",
            ]],
            show_progress_bar=False,
        )
        return True
    except Exception as exc:  # pragma: no cover - depends on local model availability.
        _report_load_error(exc)
        return False


def rerank_candidates(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    weight: float = RERANKER_WEIGHT,
) -> list[dict[str, Any]]:
    """Rerank the complete merged candidate set with a cross-encoder.

    ``weight`` controls how much the cross-encoder may alter the already strong
    hybrid ranking. With the calibrated default of 0.25, the final retrieval
    score is:

        75% hybrid score + 25% normalised cross-encoder score

    The final list is ordered by that blended score, not by the raw reranker
    logit. Raw values and ranks remain attached for evaluation/debugging.
    """
    if not candidates or not ENABLE_RERANKER:
        return [
            {
                **candidate,
                "rerankerApplied": False,
            }
            for candidate in candidates
        ]

    try:
        model = get_reranker()
        query_variants = (
            build_query_variants(query)
            if requires_language_bridge(query)
            else [str(query or "")]
        ) or [str(query or "")]
        pairs = [
            [variant, str(candidate.get("content") or "")]
            for candidate in candidates
            for variant in query_variants
        ]
        predictions = model.predict(
            pairs,
            show_progress_bar=False,
        )
    except Exception as exc:  # pragma: no cover - depends on local model availability.
        _report_load_error(exc)
        return [
            {
                **candidate,
                "rerankerApplied": False,
            }
            for candidate in candidates
        ]

    flat_raw_values: list[float] = []
    for raw in predictions:
        try:
            flat_raw_values.append(float(raw))
        except (TypeError, ValueError):
            flat_raw_values.append(0.0)

    variant_count = max(len(query_variants), 1)
    raw_values: list[float] = []
    best_variant_by_candidate: list[str] = []
    variant_raw_scores: list[dict[str, float]] = []
    for candidate_index in range(len(candidates)):
        start = candidate_index * variant_count
        values = flat_raw_values[start:start + variant_count]
        if not values:
            values = [0.0]
        best_index = max(range(len(values)), key=lambda index: values[index])
        raw_values.append(values[best_index])
        best_variant_by_candidate.append(query_variants[best_index])
        variant_raw_scores.append({
            query_variants[index]: round(values[index], 6)
            for index in range(min(len(values), len(query_variants)))
        })

    normalised_scores = _normalise_logits(raw_values)
    raw_order = sorted(
        range(len(raw_values)),
        key=lambda index: raw_values[index],
        reverse=True,
    )
    raw_rank_by_index = {
        candidate_index: rank
        for rank, candidate_index in enumerate(raw_order, start=1)
    }

    safe_weight = max(0.0, min(float(weight), 1.0))
    scored: list[dict[str, Any]] = []

    for index, candidate in enumerate(candidates):
        raw_value = raw_values[index]
        reranker_score = normalised_scores[index]
        hybrid_score = float(
            candidate.get("baseScore")
            if candidate.get("baseScore") is not None
            else candidate.get("score") or 0.0
        )
        hybrid_score = max(0.0, min(hybrid_score, 1.0))
        blended_score = (
            (1.0 - safe_weight) * hybrid_score
            + safe_weight * reranker_score
        )

        scored.append(
            {
                **candidate,
                "baseScore": round(hybrid_score, 6),
                "rerankerApplied": True,
                "rerankerModel": RERANKER_MODEL,
                "rerankerWeight": round(safe_weight, 6),
                "rerankerRawScore": round(raw_value, 6),
                "rerankerRawRank": raw_rank_by_index[index],
                "rerankerQueryVariant": best_variant_by_candidate[index],
                "rerankerVariantRawScores": variant_raw_scores[index],
                "rerankerScore": round(reranker_score, 6),
                "score": round(max(0.0, min(blended_score, 1.0)), 6),
            }
        )

    # The blended final score controls ranking. Cross-encoder and base scores are
    # deterministic tie-breakers only.
    scored.sort(
        key=lambda row: (
            float(row.get("score") or 0.0),
            float(row.get("rerankerScore") or 0.0),
            float(row.get("baseScore") or 0.0),
            float(row.get("rerankerRawScore") or 0.0),
        ),
        reverse=True,
    )

    return [
        {
            **row,
            "rerankerRank": index,
        }
        for index, row in enumerate(scored, start=1)
    ]
