"""Conservative answerability gate for retrieval results.

A reranker can only reorder candidates. It cannot decide that the indexed corpus
contains no answer. This module adds a separate rejection stage after hybrid
retrieval, cross-encoder reranking, and evidence verification.

The gate combines:
- an absolute top-result score;
- deterministic evidence support;
- the score margin between the first and second candidate;
- the number of independently supported candidates; and
- explicit detail requirements for precision-sensitive questions such as an
  exact URL, a software version, a cadence, or a monetary threshold.

The implementation is intentionally conservative: when a question asks for an
exact detail that is not literally present in the retrieved evidence, the whole
retrieval result is rejected instead of allowing the LLM to infer it.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from retrieval.query_expansion import normalize_text
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

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["failed_checks"] = list(self.failed_checks)
        payload["passed_checks"] = list(self.passed_checks)
        return payload


_URL_PATTERN = re.compile(
    r"(?:https?://|www\.)[^\s)\]}>\"']+|\b/[A-Za-z0-9_.~!$&'()*+,;=:@%/-]{3,}",
    flags=re.I,
)
_VERSION_PATTERN = re.compile(
    r"\b(?:v(?:ersion)?\s*)?\d+(?:\.\d+){1,3}\b|"
    r"\b(?:macos|windows|android|ios|crm)\s*(?:version|versi)?\s*[v.]?\s*\d+(?:\.\d+)*\b",
    flags=re.I,
)
_CADENCE_PATTERN = re.compile(
    r"\b(?:daily|weekly|monthly|quarterly|annually|yearly|biweekly|"
    r"once\s+(?:a|per)\s+(?:day|week|month|quarter|year)|"
    r"twice\s+(?:a|per)\s+(?:day|week|month|quarter|year)|"
    r"every\s+\d+\s+(?:days?|weeks?|months?|years?)|"
    r"harian|mingguan|bulanan|triwulan|kuartalan|tahunan|"
    r"setiap\s+(?:hari|minggu|bulan|triwulan|kuartal|tahun)|"
    r"\d+\s+kali\s+(?:per|setiap)\s+(?:hari|minggu|bulan|tahun))\b",
    flags=re.I,
)
_MONEY_PATTERN = re.compile(
    r"(?:\b(?:IDR|Rp)\s*\d[\d.,]*|\b\d[\d.,]*\s*(?:rupiah|IDR)\b)",
    flags=re.I,
)
_NUMBER_WITH_UNIT_PATTERN = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(GB|MB|TB|KB|days?|years?|months?|weeks?|hours?|"
    r"minutes?|seconds?|characters?|chars?|requests?|calls?|hari|tahun|bulan|minggu|jam|"
    r"menit|detik|karakter|permintaan|panggilan|%|persen|percent)(?=$|[^A-Za-z0-9])",
    flags=re.I,
)
_QUOTED_PATTERN = re.compile(r"['\"“”‘’*]([^'\"“”‘’*]{8,120})['\"“”‘’*]")


def _clamp(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(score, 1.0))


def _contains_any(text: str, phrases: Iterable[str]) -> bool:
    normalized = f" {normalize_text(text)} "
    return any(
        phrase_normalized and f" {phrase_normalized} " in normalized
        for phrase_normalized in (normalize_text(phrase) for phrase in phrases)
    )


def _normalized_literal(value: str) -> str:
    return re.sub(r"\s+", " ", normalize_text(value)).strip()


def _extract_quoted_requirements(question: str) -> list[str]:
    output: list[str] = []
    for match in _QUOTED_PATTERN.finditer(str(question or "")):
        phrase = _normalized_literal(match.group(1))
        # Ignore emphasis around one generic word. Exact multi-word names are
        # useful answerability constraints; markdown styling alone is not.
        if len(phrase.split()) >= 3 and phrase not in output:
            output.append(phrase)
    return output


def _explicit_numeric_constraints(question: str) -> list[tuple[str, str]]:
    constraints: list[tuple[str, str]] = []
    for number, unit in _NUMBER_WITH_UNIT_PATTERN.findall(str(question or "")):
        normalized_number = number.replace(",", ".")
        normalized_unit = unit.lower()
        aliases = {
            "day": "days",
            "hari": "days",
            "year": "years",
            "tahun": "years",
            "month": "months",
            "bulan": "months",
            "week": "weeks",
            "minggu": "weeks",
            "hour": "hours",
            "jam": "hours",
            "minute": "minutes",
            "menit": "minutes",
            "second": "seconds",
            "detik": "seconds",
            "character": "characters",
            "char": "characters",
            "karakter": "characters",
            "request": "requests",
            "call": "requests",
            "permintaan": "requests",
            "panggilan": "requests",
            "persen": "%",
            "percent": "%",
        }
        normalized_unit = aliases.get(normalized_unit, normalized_unit)
        constraint = (normalized_number, normalized_unit)
        if constraint not in constraints:
            constraints.append(constraint)
    return constraints


def _is_scenario_comparison_question(question: str) -> bool:
    """Return True when user-supplied values are a scenario, not a citation key.

    Example: "If my password has 10 characters, does it comply?" should be
    answered from a policy that states a 12-character minimum. Requiring the
    literal value ``10`` in the source would incorrectly reject the answer.
    """
    query = normalize_text(question)
    has_scenario_marker = _contains_any(
        query,
        (
            "if", "jika", "apabila", "seandainya", "suppose", "assuming",
            "ketika seorang", "ketika sebuah",
        ),
    )
    decision_terms = (
        "comply", "compliant", "mematuhi", "memenuhi", "allowed", "allow",
        "permissible", "diperbolehkan", "diizinkan", "boleh", "rejected",
        "ditolak", "violate", "melanggar", "pelanggaran", "errors", "error",
        "kesalahan", "menimbulkan", "require", "requires", "memerlukan",
    )
    has_decision_intent = any(
        re.search(rf"\b{re.escape(term)}\b", query)
        for term in decision_terms
    )
    starts_as_decision_question = bool(
        re.match(r"^(?:apakah|does|is|will|would|can|could)\b", query)
    )
    return has_decision_intent and (has_scenario_marker or starts_as_decision_question)


def _unit_family(unit: str) -> str:
    normalized = str(unit or "").lower()
    if normalized in {"gb", "mb", "tb", "kb"}:
        return "storage"
    if normalized in {
        "seconds", "minutes", "hours", "days", "weeks", "months", "years"
    }:
        return "duration"
    if normalized == "characters":
        return "length"
    if normalized == "requests":
        return "request_count"
    if normalized == "%":
        return "percentage"
    return normalized


def _content_has_numeric_family(content: str, family: str) -> bool:
    for _, unit in _explicit_numeric_constraints(content):
        if _unit_family(unit) == family:
            return True
    return False


def _content_has_numeric_constraint(content: str, number: str, unit: str) -> bool:
    number_pattern = re.escape(number).replace(r"\.", r"[.,]")
    unit_patterns = {
        "days": r"(?:days?|hari)",
        "years": r"(?:years?|tahun)",
        "months": r"(?:months?|bulan)",
        "weeks": r"(?:weeks?|minggu)",
        "hours": r"(?:hours?|hrs?|jam)",
        "minutes": r"(?:minutes?|mins?|menit)",
        "seconds": r"(?:seconds?|secs?|detik)",
        "characters": r"(?:characters?|chars?|karakter)",
        "requests": r"(?:requests?|calls?|permintaan|panggilan)",
        "%": r"(?:%|percent|persen)",
    }
    unit_pattern = unit_patterns.get(unit, re.escape(unit))
    return bool(
        re.search(
            rf"\b{number_pattern}\s*{unit_pattern}\b",
            content,
            flags=re.I,
        )
    )


def _precision_checks(question: str, evidence_text: str) -> tuple[list[str], list[str]]:
    """Return passed and failed checks for details that must be explicit."""
    query = normalize_text(question)
    evidence = str(evidence_text or "")
    evidence_normalized = normalize_text(evidence)
    passed: list[str] = []
    failed: list[str] = []

    def record(name: str, condition: bool) -> None:
        (passed if condition else failed).append(name)

    asks_exact_endpoint = (
        _contains_any(query, ("exact url", "exact endpoint", "direct url", "url endpoint", "url persis", "endpoint persis"))
        or (
            _contains_any(query, ("url", "endpoint", "link"))
            and _contains_any(query, ("exact", "persis", "langsung", "direct"))
        )
    )
    if asks_exact_endpoint:
        url_present = bool(_URL_PATTERN.search(evidence))
        subject_present = True
        if _contains_any(query, ("password reset", "reset password", "setel ulang kata sandi", "active directory")):
            subject_present = _contains_any(
                evidence_normalized,
                ("password reset", "reset password", "setel ulang kata sandi", "active directory"),
            )
        record("explicit_url_or_endpoint", url_present and subject_present)

    asks_version = (
        _contains_any(query, ("version number", "specific version", "nomor versi", "versi spesifik", "versi minimum", "minimum version"))
        or (
            _contains_any(query, ("version", "versi"))
            and _contains_any(query, ("software", "perangkat lunak", "aplikasi", "crm", "macos", "windows"))
        )
    )
    if asks_version:
        record("explicit_version", bool(_VERSION_PATTERN.search(evidence)))

    asks_frequency = _contains_any(
        query,
        ("how frequently", "how often", "seberapa sering", "berapa kali", "testing schedule", "jadwal pelaksanaan"),
    )
    if asks_frequency:
        record("explicit_frequency", bool(_CADENCE_PATTERN.search(evidence)))

    asks_money = (
        _contains_any(query, ("nilai nominal", "nominal value", "in idr", "dalam mata uang rupiah", "batas hadiah", "gift value"))
        or (
            _contains_any(query, ("maximum", "maksimum", "maksimal"))
            and _contains_any(query, ("gift", "hadiah", "bingkisan", "vendor"))
        )
    )
    if asks_money:
        money_present = bool(_MONEY_PATTERN.search(evidence))
        gift_subject_present = True
        if _contains_any(query, ("gift", "hadiah", "bingkisan", "vendor")):
            gift_subject_present = _contains_any(
                evidence_normalized,
                ("gift", "hadiah", "bingkisan", "vendor", "supplier"),
            )
        record("explicit_monetary_value", money_present and gift_subject_present)

    asks_monthly_benefit = (
        _contains_any(query, ("monthly", "bulanan"))
        and _contains_any(query, ("subsidy", "allowance", "benefit", "subsidi", "tunjangan"))
    )
    if asks_monthly_benefit:
        record(
            "explicit_monthly_benefit",
            _contains_any(evidence_normalized, ("monthly", "per month", "each month", "bulanan", "setiap bulan")),
        )

    asks_paternity = _contains_any(
        query,
        ("paternity leave", "cuti ayah", "karyawan pria", "male employee", "spouse gives birth", "pasangannya melahirkan"),
    )
    if asks_paternity:
        record(
            "paternity_leave_subject",
            _contains_any(
                evidence_normalized,
                ("paternity leave", "cuti ayah", "father", "male employee", "spouse gives birth", "pasangan melahirkan"),
            ),
        )

    asks_relocation = _contains_any(query, ("relocation allowance", "tunjangan relokasi", "relocation program", "program relokasi"))
    if asks_relocation:
        record(
            "relocation_allowance_subject",
            _contains_any(evidence_normalized, ("relocation allowance", "tunjangan relokasi", "relocation program", "program relokasi")),
        )

    if _contains_any(query, ("tokyo branch", "cabang tokyo", "tokyo branch office", "kantor cabang tokyo")):
        record("tokyo_branch_subject", _contains_any(evidence_normalized, ("tokyo",)))

    asks_projection = _contains_any(query, ("projected", "projection", "forecast", "proyeksi", "diproyeksikan"))
    if asks_projection:
        record(
            "projection_not_historical_value",
            _contains_any(evidence_normalized, ("projected", "projection", "forecast", "proyeksi", "diproyeksikan", "outlook")),
        )

    asks_crm = _contains_any(query, ("crm", "customer relationship management"))
    if asks_crm:
        record("crm_subject", _contains_any(evidence_normalized, ("crm", "customer relationship management")))

    asks_archive_procedure = (
        _contains_any(query, ("archive", "archiving", "arsip", "mengarsipkan"))
        and _contains_any(query, ("procedure", "prosedur", "langkah", "systematic"))
    )
    if asks_archive_procedure:
        record("archive_procedure", _contains_any(evidence_normalized, ("archive", "archiving", "arsip", "mengarsipkan")))

    for phrase in _extract_quoted_requirements(question):
        record(f"quoted_phrase:{phrase}", phrase in evidence_normalized)

    numeric_constraints = _explicit_numeric_constraints(question)
    if _is_scenario_comparison_question(question):
        # In compliance/counterfactual questions, values supplied by the user
        # describe a scenario. The source normally contains a different policy
        # threshold (10 characters in the question versus a 12-character
        # minimum in the policy). Require an explicit threshold of the same
        # measurement family instead of the exact scenario value.
        for family in sorted({_unit_family(unit) for _, unit in numeric_constraints}):
            record(
                f"scenario_threshold:{family}",
                _content_has_numeric_family(evidence, family),
            )
    else:
        # In lookup/procedure questions, supplied numbers identify the exact
        # condition being asked about and therefore must occur in evidence.
        for number, unit in numeric_constraints:
            record(
                f"explicit_constraint:{number}_{unit}",
                _content_has_numeric_constraint(evidence, number, unit),
            )

    return passed, failed


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
    """Assess whether retrieved evidence is strong enough to permit an answer."""
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

    ranked = sorted(
        candidates,
        key=lambda row: _clamp(row.get("score")),
        reverse=True,
    )
    top = ranked[0]
    top_score = _clamp(top.get("score"))
    top_base_score = _clamp(
        top.get("baseScore")
        if top.get("baseScore") is not None
        else top_score
    )
    top_evidence_score = _clamp(top.get("evidenceScore"))
    top_exact_coverage = _clamp(top.get("exactTokenCoverage"))
    second_score = _clamp(ranked[1].get("score")) if len(ranked) > 1 else 0.0
    score_margin = max(0.0, top_score - second_score)

    supporting_candidate_count = sum(
        1
        for candidate in ranked[: max(int(max_contexts), 1)]
        if candidate.get("evidenceSupported") is True
        and _clamp(candidate.get("evidenceScore")) >= min_evidence_score
        and not candidate.get("evidenceHardFailures")
    )

    # Precision-sensitive details must be present in the top supporting source.
    # Combining unrelated top-k chunks could otherwise satisfy an exact URL or
    # amount requirement accidentally.
    precision_evidence_text = str(top.get("content") or "")
    precision_passed, precision_failed = _precision_checks(
        question,
        precision_evidence_text,
    )

    passed: list[str] = list(precision_passed)
    failed: list[str] = list(precision_failed)

    if top_score >= min_top_score:
        passed.append("minimum_top_score")
    else:
        failed.append("minimum_top_score")

    # The cross-encoder is only a second-stage ordering signal. A candidate
    # whose original hybrid score is weak cannot become answerable solely
    # because the reranker assigned it a high relative score.
    if top_base_score >= min_base_score:
        passed.append("minimum_base_hybrid_score")
    else:
        failed.append("minimum_base_hybrid_score")

    if top.get("evidenceHardFailures"):
        failed.append("top_candidate_hard_failure")

    strong_retrieval_fallback = (
        top_score >= ANSWERABILITY_STRONG_RETRIEVAL_SCORE
        and top_base_score >= min_base_score
        and top_exact_coverage >= ANSWERABILITY_STRONG_EXACT_COVERAGE
    )

    if supporting_candidate_count > 0:
        passed.append("supported_evidence")
    elif strong_retrieval_fallback:
        passed.append("strong_retrieval_fallback")
    elif require_supported_evidence:
        failed.append("supported_evidence")

    # A small top-1/top-2 margin is not a rejection by itself. It becomes a
    # rejection signal only when the top result is also weak and unsupported.
    ambiguous_ranking = (
        len(ranked) > 1
        and score_margin < min_score_margin
        and top_score < ANSWERABILITY_STRONG_RETRIEVAL_SCORE
        and supporting_candidate_count == 0
    )
    if ambiguous_ranking:
        failed.append("ambiguous_top_margin")
    else:
        passed.append("top_margin_or_support")

    # Confidence is descriptive; hard precision checks still control the final
    # decision. This number is useful in logs and evaluation reports.
    support_signal = min(supporting_candidate_count / 2.0, 1.0)
    margin_signal = min(score_margin / max(min_score_margin, 1e-6), 1.0)
    answerability_score = (
        0.35 * top_score
        + 0.20 * top_base_score
        + 0.25 * top_evidence_score
        + 0.08 * top_exact_coverage
        + 0.08 * support_signal
        + 0.04 * margin_signal
    )
    answerability_score = _clamp(answerability_score)

    answerable = not failed
    if answerable:
        reason = "Retrieval contains explicit, sufficiently supported evidence."
    else:
        reason = "Retrieval rejected: " + ", ".join(failed)

    return AnswerabilityDecision(
        answerable=answerable,
        score=round(answerability_score, 6),
        reason=reason,
        failed_checks=tuple(dict.fromkeys(failed)),
        passed_checks=tuple(dict.fromkeys(passed)),
        top_score=round(top_score, 6),
        top_base_score=round(top_base_score, 6),
        top_evidence_score=round(top_evidence_score, 6),
        top_exact_coverage=round(top_exact_coverage, 6),
        score_margin=round(score_margin, 6),
        supporting_candidate_count=supporting_candidate_count,
        precision_requirement_count=len(precision_passed) + len(precision_failed),
    )


def apply_answerability_gate(
    question: str,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return annotated candidates, or an empty list when evidence is insufficient."""
    decision = assess_answerability(question, candidates)
    if not decision.answerable:
        print(f"[ANSWERABILITY] Rejected query: {decision.reason}")
        return []

    metadata = decision.to_dict()
    return [
        {
            **candidate,
            "answerabilityAccepted": True,
            "answerabilityScore": decision.score,
            "answerabilityReason": decision.reason,
            "answerabilityScoreMargin": decision.score_margin,
            "answerabilitySupportingCandidates": decision.supporting_candidate_count,
            "answerabilityPrecisionRequirementCount": decision.precision_requirement_count,
            "answerabilityDiagnostics": metadata,
        }
        for candidate in candidates
    ]
