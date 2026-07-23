"""Shared retrieval scoring helpers.

The hybrid retriever combines semantic and lexical signals. A missing signal
must not be treated as a real zero-value vote because that disproportionately
penalizes cross-language queries, where multilingual embeddings remain valid
while BM25 may have no literal token overlap.
"""

from __future__ import annotations

from collections.abc import Iterable


def clamp_score(value: object) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(score, 1.0))


def normalized_weighted_score(
    signals: Iterable[tuple[float, object]],
) -> float:
    """Blend only positive, available relevance signals.

    Thresholds are deliberately not changed. This function only prevents an
    unavailable retriever from diluting another retriever that produced a real
    score. When semantic and lexical signals are both available, the configured
    weights preserve the original 68/32 hybrid formula.
    """
    weighted_total = 0.0
    active_weight = 0.0

    for raw_weight, raw_score in signals:
        weight = max(float(raw_weight), 0.0)
        score = clamp_score(raw_score)
        if weight <= 0.0 or score <= 0.0:
            continue
        weighted_total += weight * score
        active_weight += weight

    if active_weight <= 0.0:
        return 0.0
    return clamp_score(weighted_total / active_weight)


def hybrid_base_score(semantic_score: object, keyword_score: object) -> float:
    """Return the calibrated semantic/BM25 score using active-signal weights."""
    return normalized_weighted_score(
        (
            (0.68, semantic_score),
            (0.32, keyword_score),
        )
    )
