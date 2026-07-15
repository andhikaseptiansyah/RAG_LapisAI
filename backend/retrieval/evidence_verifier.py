"""Deterministic evidence verification for retrieved chunks.

Similarity answers "which text is closest?". Evidence verification answers the
more important question: "does this chunk actually contain the constraints and
concepts needed to answer the question?" The verifier is intentionally
conservative and transparent; it never invents an answer.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from retrieval.query_expansion import (
    CONCEPT_ALIASES,
    concepts_in_text,
    contains_alias,
    normalize_text,
)


@dataclass(frozen=True)
class EvidenceDecision:
    supported: bool
    score: float
    concept_coverage: float
    matched_concepts: tuple[str, ...]
    missing_concepts: tuple[str, ...]
    hard_failures: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["matched_concepts"] = list(self.matched_concepts)
        payload["missing_concepts"] = list(self.missing_concepts)
        payload["hard_failures"] = list(self.hard_failures)
        return payload


# Missing one of these usually changes the subject of the answer, not merely its
# wording. They therefore act as hard constraints when explicitly asked.
HARD_CONCEPTS = {
    "password_reset",
    "maternity_leave",
    "paternity_leave",
    "annual_leave",
    "carryover",
    "original_receipt",
    "access_revocation",
    "offboarding",
    "revenue",
    "water",
    "electricity",
    "subsidy",
    "canteen",
    "macos",
    "minimum_version",
    "data_breach",
    "information_classification",
    "audit_log",
    "rto",
    "rpo",
    "api_token",
}

# Generic concepts help scoring but should not independently reject a candidate.
SOFT_CONCEPTS = {
    "office",
    "supported",
    "laptop",
    "system_access",
    "expense",
    "reduction",
    "full_year",
    "processing_time",
    "amount_threshold",
    "helpdesk",
    "password",
    "next_year",
}

STOPWORDS = {
    "apa", "apakah", "bagaimana", "berapa", "lama", "yang", "dan", "atau",
    "di", "ke", "dari", "untuk", "dengan", "pada", "dalam", "sebesar",
    "what", "which", "how", "many", "much", "long", "is", "are", "was",
    "were", "the", "a", "an", "of", "to", "in", "on", "for", "with",
    "company", "employee", "employees", "perusahaan", "karyawan", "pegawai",
}

TIME_PATTERN = re.compile(
    r"\b(?:within\s+)?(?:\d+\s*x\s*\d+|\d+(?:[.,]\d+)?)\s*"
    r"(?:minutes?|mins?|hours?|hrs?|days?|working\s+days?|business\s+days?|weeks?|months?|years?|"
    r"menit|jam|hari|minggu|bulan|tahun)\b",
    flags=re.I,
)

NUMBER_PATTERN = re.compile(
    r"(?:\bIDR\s*)?\b\d[\d.,]*(?:\s*(?:%|percent|persen|billion|million|juta|miliar))?\b",
    flags=re.I,
)

VERSION_PATTERN = re.compile(
    r"\b(?:version|versi|macos|windows|android|ios)\s*[v.]?\s*\d+(?:\.\d+)*\b",
    flags=re.I,
)


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9à-ÿ]+", normalize_text(text))
    return {
        token
        for token in tokens
        if len(token) > 2 and token not in STOPWORDS
    }


def _years(text: str) -> set[str]:
    return set(re.findall(r"\b(?:19|20)\d{2}\b", str(text or "")))


def _has_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    """Match complete normalized words/phrases, never raw substrings.

    This prevents short markers such as ``rto`` from matching ``corporate`` and
    ``when`` from matching longer unrelated tokens.
    """
    normalized = normalize_text(text)
    padded = f" {normalized} "
    return any(
        candidate and f" {candidate} " in padded
        for candidate in (normalize_text(phrase) for phrase in phrases)
    )


def _percent_requested(question: str) -> bool:
    return "%" in str(question) or _has_phrase(question, ("persen", "percent", "percentage"))


def _numeric_answer_requested(question: str) -> bool:
    return _has_phrase(
        question,
        (
            "berapa",
            "how many",
            "how much",
            "how long",
            "what percentage",
            "which version",
            "what version",
            "minimum version",
            "versi minimum",
            "when",
            "kapan",
            "paling lambat",
            "maksimal",
            "maximum",
        ),
    )


def _duration_requested(question: str) -> bool:
    concepts = set(concepts_in_text(question))
    return (
        "processing_time" in concepts
        or "rto" in concepts
        or "rpo" in concepts
        or _has_phrase(
            question,
            (
                "berapa lama",
                "batas waktu",
                "time limit",
                "maximum time",
                "maximum processing time",
                "how long",
                "within how long",
                "paling lambat",
                "lama proses",
                "waktu proses",
                "acknowledgement",
                "resolution target",
            ),
        )
    )


def _amount_requested(question: str) -> bool:
    # Do not treat every use of "maximum/minimum" as money. For example,
    # "maximum mailbox storage" is numeric but not a monetary amount.
    return _has_phrase(
        question,
        (
            "sebesar berapa",
            "berapa biaya",
            "berapa nominal",
            "nominal maksimal",
            "batas nominal",
            "how much",
            "what amount",
            "what cost",
            "maximum reimbursement",
            "minimum reimbursement",
            "financial penalty",
        ),
    )


def _concept_match(canonical: str, content: str) -> bool:
    normalized = normalize_text(content)
    if canonical == "password_reset":
        return bool(re.search(r"\breset(?:s|ting|ted)?\b", normalized)) and "password" in normalized
    if canonical == "access_revocation":
        return bool(re.search(r"\brevok(?:e|es|ed|ing)\b", normalized)) and "access" in normalized
    if canonical == "processing_time":
        return bool(TIME_PATTERN.search(content)) or contains_alias(
            content,
            CONCEPT_ALIASES[canonical],
        )
    if canonical == "amount_threshold":
        return bool(NUMBER_PATTERN.search(content)) and (
            "above" in normalize_text(content)
            or "maximum" in normalize_text(content)
            or "minimum" in normalize_text(content)
            or "capped" in normalize_text(content)
            or "idr" in normalize_text(content)
        )
    if canonical == "minimum_version":
        return bool(VERSION_PATTERN.search(content))
    return contains_alias(content, CONCEPT_ALIASES[canonical])


def _lexical_coverage(question: str, content: str) -> float:
    query_tokens = _tokenize(question)
    if not query_tokens:
        return 1.0
    content_tokens = _tokenize(content)
    matched = 0
    for token in query_tokens:
        if token in content_tokens:
            matched += 1
            continue
        # A light morphology fallback handles plural/inflection without fuzzy
        # matching unrelated short words.
        if len(token) >= 5 and any(
            candidate.startswith(token[:5]) or token.startswith(candidate[:5])
            for candidate in content_tokens
            if len(candidate) >= 5
        ):
            matched += 1
    return matched / max(len(query_tokens), 1)


def verify_evidence(
    question: str,
    content: str,
    *,
    minimum_score: float = 0.58,
) -> EvidenceDecision:
    """Evaluate one candidate chunk against the full question.

    The score combines bilingual concept coverage, lexical coverage, and explicit
    constraints. A hard failure is raised when a requested year, platform, leave
    type, resource type, or other subject-defining concept is absent.
    """
    question_text = str(question or "").strip()
    content_text = str(content or "").strip()

    if not question_text or not content_text:
        return EvidenceDecision(
            supported=False,
            score=0.0,
            concept_coverage=0.0,
            matched_concepts=(),
            missing_concepts=(),
            hard_failures=("empty_content",),
            reason="Question or candidate content is empty.",
        )

    required = concepts_in_text(question_text)
    matched: list[str] = []
    missing: list[str] = []

    for canonical in required:
        if _concept_match(canonical, content_text):
            matched.append(canonical)
        else:
            missing.append(canonical)

    concept_coverage = (
        len(matched) / len(required)
        if required
        else 1.0
    )
    lexical_coverage = _lexical_coverage(question_text, content_text)

    hard_failures: list[str] = []

    question_years = _years(question_text)
    content_years = _years(content_text)
    for year in sorted(question_years):
        if year not in content_years:
            hard_failures.append(f"missing_year:{year}")

    for canonical in missing:
        if canonical in HARD_CONCEPTS:
            hard_failures.append(f"missing_concept:{canonical}")

    if _duration_requested(question_text) and not TIME_PATTERN.search(content_text):
        hard_failures.append("missing_duration_value")

    if _amount_requested(question_text) and not NUMBER_PATTERN.search(content_text):
        hard_failures.append("missing_numeric_value")

    if _percent_requested(question_text):
        normalized_content = normalize_text(content_text)
        if "%" not in content_text and "percent" not in normalized_content and "persen" not in normalized_content:
            hard_failures.append("missing_percentage")

    if "minimum_version" in required and not VERSION_PATTERN.search(content_text):
        hard_failures.append("missing_version_value")

    # Numeric questions need an explicit numeric or time expression. This keeps a
    # broadly related policy from being treated as evidence for a precise answer.
    numeric_support = 1.0
    if _numeric_answer_requested(question_text):
        numeric_support = 1.0 if (
            NUMBER_PATTERN.search(content_text)
            or TIME_PATTERN.search(content_text)
            or VERSION_PATTERN.search(content_text)
        ) else 0.0

    if required:
        concept_weight = 0.68
        lexical_weight = 0.17
        numeric_weight = 0.15
    else:
        # Unknown topics are not rejected merely because they are absent from the
        # enterprise lexicon; lexical support remains a safe fallback.
        concept_weight = 0.25
        lexical_weight = 0.60
        numeric_weight = 0.15

    score = (
        concept_weight * concept_coverage
        + lexical_weight * lexical_coverage
        + numeric_weight * numeric_support
    )
    score = max(0.0, min(float(score), 1.0))

    supported = not hard_failures and (score + 1e-9) >= minimum_score
    if hard_failures:
        reason = "Evidence is missing a subject-defining constraint: " + ", ".join(hard_failures)
    elif supported:
        reason = "Candidate contains sufficient concepts and explicit evidence."
    else:
        reason = (
            f"Evidence score {score:.3f} is below the minimum {minimum_score:.3f}."
        )

    return EvidenceDecision(
        supported=supported,
        score=round(score, 6),
        concept_coverage=round(concept_coverage, 6),
        matched_concepts=tuple(sorted(set(matched))),
        missing_concepts=tuple(sorted(set(missing))),
        hard_failures=tuple(sorted(set(hard_failures))),
        reason=reason,
    )


def verify_chunks(
    question: str,
    chunks: list[dict[str, Any]],
    *,
    minimum_score: float = 0.58,
) -> list[dict[str, Any]]:
    """Annotate chunks with evidence information without mutating the originals."""
    annotated: list[dict[str, Any]] = []
    for chunk in chunks:
        decision = verify_evidence(
            question,
            str(chunk.get("content") or ""),
            minimum_score=minimum_score,
        )
        annotated.append(
            {
                **chunk,
                "evidenceSupported": decision.supported,
                "evidenceScore": decision.score,
                "evidenceCoverage": decision.concept_coverage,
                "evidenceMissingConcepts": list(decision.missing_concepts),
                # A requirement missing from one chunk is not a contradiction.
                # Another chunk in the bundle may satisfy it. Keep the original
                # diagnostics, but reserve hard failures for actual conflicts.
                "evidenceMissingRequirements": list(decision.hard_failures),
                "evidenceHardFailures": [],
                "evidenceContradictions": [],
                "evidenceReason": decision.reason,
            }
        )
    return annotated
