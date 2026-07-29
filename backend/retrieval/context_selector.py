"""Select a compact, non-redundant evidence bundle for generation.

Retrieval keeps top-k results for evaluation and recall. This module is used only
before generation and citations, so the LLM sees the smallest bundle that covers
the explicit requirements of the question.
"""

from __future__ import annotations

import re
from typing import Any

from retrieval.requirements import extract_evidence_requirements, requirement_satisfied
from retrieval.query_expansion import normalize_text

_STOPWORDS = {
    "apa", "apakah", "bagaimana", "berapa", "yang", "dan", "atau", "untuk", "dengan",
    "what", "which", "how", "the", "and", "or", "for", "with", "from", "into",
    "company", "employee", "employees", "perusahaan", "karyawan",
}


def _score(row: dict[str, Any]) -> float:
    try:
        return max(0.0, min(float(row.get("score") or 0.0), 1.0))
    except (TypeError, ValueError):
        return 0.0


def _tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9à-ÿ]+", normalize_text(text))
        if len(token) >= 3 and token not in _STOPWORDS
    }


def _jaccard(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _document_name(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") or {}
    return str(
        row.get("documentName")
        or row.get("document_name")
        or metadata.get("filename")
        or "-"
    )


def _requirement_keys(question: str, content: str) -> set[str]:
    keys: set[str] = set()
    for requirement in extract_evidence_requirements(question):
        if requirement_satisfied(requirement, [content]):
            keys.add(requirement.key)
    return keys


def select_context_bundle(
    question: str,
    candidates: list[dict[str, Any]],
    *,
    max_contexts: int = 3,
    minimum_contexts: int = 1,
    redundancy_threshold: float = 0.82,
    secondary_score_ratio: float = 0.72,
) -> list[dict[str, Any]]:
    """Return a compact evidence set while preserving requirement coverage.

    The first candidate is retained when available. Additional candidates are
    selected only when they cover a missing requirement, add a different source,
    or provide meaningfully different text at a sufficiently strong score.
    """
    if not candidates:
        return []

    limit = max(1, int(max_contexts))
    target_minimum = min(limit, max(1, int(minimum_contexts)))
    ranked = sorted(candidates, key=_score, reverse=True)
    requirements = extract_evidence_requirements(question)
    all_requirement_keys = {item.key for item in requirements}
    question_tokens = _tokens(question)

    enriched: list[dict[str, Any]] = []
    for row in ranked:
        content = str(row.get("content") or "")
        coverage = _requirement_keys(question, content)
        enriched.append({
            **row,
            "contextRequirementCoverage": sorted(coverage),
            "contextDocument": _document_name(row),
        })

    selected: list[dict[str, Any]] = []
    covered: set[str] = set()
    top_score = max(_score(enriched[0]), 1e-6)

    while enriched and len(selected) < limit:
        best_index: int | None = None
        best_utility = float("-inf")

        for index, row in enumerate(enriched):
            content = str(row.get("content") or "")
            requirement_gain = len(set(row["contextRequirementCoverage"]) - covered)
            redundancy = max(
                (_jaccard(content, str(chosen.get("content") or "")) for chosen in selected),
                default=0.0,
            )
            new_document = not any(
                row["contextDocument"].casefold() == chosen.get("contextDocument", "").casefold()
                for chosen in selected
            )

            # Keep the first result. Afterwards, reject near-duplicate passages
            # unless they satisfy a requirement not covered by the current set.
            if selected and redundancy >= redundancy_threshold and requirement_gain == 0:
                continue

            relative_score = _score(row) / top_score
            if selected and requirement_gain == 0 and relative_score < secondary_score_ratio:
                continue
            if selected and requirement_gain == 0 and len(selected) < target_minimum:
                supports_existing_requirement = bool(
                    set(row["contextRequirementCoverage"]) & all_requirement_keys
                )
                lexical_overlap = len(question_tokens & _tokens(content))
                required_overlap = min(2, max(1, len(question_tokens)))
                if not supports_existing_requirement and lexical_overlap < required_overlap:
                    continue

            utility = (
                2.4 * requirement_gain
                + 0.85 * _score(row)
                + (0.12 if new_document else 0.0)
                - 0.65 * redundancy
            )
            if not selected and index == 0:
                utility += 1.0

            if utility > best_utility:
                best_utility = utility
                best_index = index

        if best_index is None:
            break

        chosen = enriched.pop(best_index)
        selected.append(chosen)
        covered.update(chosen["contextRequirementCoverage"])

        # Keep up to the requested minimum when another strong, relevant,
        # non-redundant passage exists. This gives generation enough evidence
        # for a short explanatory paragraph without forcing unrelated sources.
        if (
            all_requirement_keys
            and covered >= all_requirement_keys
            and len(selected) >= target_minimum
        ):
            break
        if not all_requirement_keys and len(selected) >= target_minimum:
            break

    # If requirements remain uncovered, add the strongest non-duplicate rows up
    # to the limit. This preserves recall for multi-part questions without
    # returning every retrieval candidate.
    if all_requirement_keys - covered:
        for row in enriched:
            if len(selected) >= limit:
                break
            content = str(row.get("content") or "")
            if any(_jaccard(content, str(chosen.get("content") or "")) >= 0.92 for chosen in selected):
                continue
            selected.append(row)
            covered.update(row["contextRequirementCoverage"])
            if covered >= all_requirement_keys:
                break

    return [
        {
            **row,
            "contextSelected": True,
            "contextSelectionRank": index,
            "contextBundleCoveredRequirements": sorted(covered),
            "contextBundleMissingRequirements": sorted(all_requirement_keys - covered),
        }
        for index, row in enumerate(selected, start=1)
    ]
