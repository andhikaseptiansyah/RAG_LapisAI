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
    semantic_support: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["matched_concepts"] = list(self.matched_concepts)
        payload["missing_concepts"] = list(self.missing_concepts)
        payload["hard_failures"] = list(self.hard_failures)
        return payload


# Missing one of these usually changes the subject of the answer, not merely its
# wording. They therefore act as hard constraints when explicitly asked.
HARD_CONCEPTS = {
    "remote_work",
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
    "file_upload",
    "customer_portal",
    "mailbox_quota",
    "incident_p1",
    "incident_p2",
    "overtime_payment",
    "retirement_benefit",
    "calendar_sharing",
    "access_card_replacement",
    "employee_parking",
    "bank_account_update",
    "onboarding_documents",
    "phishing_report",
    "lost_company_device",
    "software_access",
    "software_license",
    "harassment_reporting",
    "byod",
    "conflict_of_interest",
    "device_security",
    "classification_levels",
    "restricted_data",
    "sick_leave",
    "medical_certificate",
    "password_complexity",
    "password_rotation",
    "password_history",
    "hotel_limit",
    "vpn_access",
    "mfa",
    "core_hours",
    "database_backup",
    "expense_claim",
    "per_diem",
    "outage_root_cause",
    "csat",
    "nps",
    "security_incident",
    "database_platform",
    "api_availability",
    "audit_retention",
    "unit_test_coverage",
    "home_office_allowance",
    "headquarters_address",
    "dr_failover",
    "email_attachment",
    "procurement_approval",
    "remote_work_eligibility",
    "hiring_headcount",
    "customer_growth",
    "laptop_request",
    "profit_margin",
    "salary_payment",
    "payslip",
    "dependents",
    "health_insurance",
    "probation",
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
    "access_card",
    "mdm",
}


MUTUALLY_EXCLUSIVE_CONCEPT_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"file_upload", "mailbox_quota"}),
    frozenset({"incident_p1", "incident_p2"}),
)

STOPWORDS = {
    "apa", "apakah", "bagaimana", "berapa", "lama", "yang", "dan", "atau",
    "di", "ke", "dari", "untuk", "dengan", "pada", "dalam", "sebesar",
    "what", "which", "how", "many", "much", "long", "is", "are", "was",
    "were", "the", "a", "an", "of", "to", "in", "on", "for", "with",
    "company", "employee", "employees", "perusahaan", "karyawan", "pegawai",
}

TIME_PATTERN = re.compile(
    r"\b(?:within\s+)?(?:"
    r"\d+\s*x\s*\d+|\d+(?:[.,]\d+)?|"
    r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"satu|dua|tiga|empat|lima|enam|tujuh|delapan|sembilan|sepuluh|sebelas|dua\s+belas"
    r")\s*"
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

RELATIVE_DATE_TIME_PATTERN = re.compile(
    r"\b(?:"
    r"(?:the\s+)?(?:next|following|previous|prior)\s+(?:working\s+day|business\s+day|"
    r"day|week|month|year|payroll(?:\s+cycle)?)|"
    r"(?:next|following)\s+month(?:'s)?\s+payroll|"
    r"payroll\s+(?:cycle\s+)?(?:of\s+)?(?:the\s+)?(?:next|following)\s+month|"
    r"(?:hari\s+kerja|hari|minggu|bulan|tahun|payroll)\s+(?:sebelumnya|berikutnya)|"
    r"siklus\s+payroll\s+(?:bulan\s+)?berikutnya|"
    r"payroll\s+bulan\s+berikutnya"
    r")\b",
    flags=re.I,
)


def _clamp_score(value: object) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(score, 1.0))


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
        english_reset = (
            bool(re.search(r"\breset(?:s|ting|ted)?\b", normalized))
            and "password" in normalized
        )
        indonesian_reset = (
            bool(re.search(r"\b(?:mereset|reset|setel ulang|atur ulang)\b", normalized))
            and ("kata sandi" in normalized or "sandi" in normalized)
        )
        return english_reset or indonesian_reset
    if canonical == "access_revocation":
        english_revoke = (
            bool(re.search(r"\brevok(?:e|es|ed|ing)\b", normalized))
            and "access" in normalized
        )
        indonesian_revoke = (
            bool(re.search(r"\b(?:mencabut|dicabut|pencabutan|menonaktifkan|dinonaktifkan)\b", normalized))
            and "akses" in normalized
        )
        return english_revoke or indonesian_revoke
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
    if canonical == "password_complexity":
        has_password = "password" in normalized or "kata sandi" in normalized
        complexity_markers = (
            bool(re.search(r"\b(?:at least|minimal)\s+\d+\s+(?:characters?|karakter)\b", normalized)),
            "uppercase" in normalized or "huruf besar" in normalized,
            "lowercase" in normalized or "huruf kecil" in normalized,
            bool(re.search(r"\b(?:number|digit|angka)\b", normalized)),
            bool(re.search(r"\b(?:symbol|special character|simbol|karakter khusus)\b", normalized)),
        )
        return has_password and sum(bool(item) for item in complexity_markers) >= 3
    if canonical == "password_rotation":
        has_password = "password" in normalized or "kata sandi" in normalized
        return has_password and bool(
            re.search(
                r"\b(?:change|changed|rotate|rotation|expire|expiry|diganti|penggantian)\b",
                normalized,
            )
        ) and bool(TIME_PATTERN.search(content) or NUMBER_PATTERN.search(content))
    if canonical == "password_history":
        has_password = "password" in normalized or "kata sandi" in normalized
        return has_password and bool(
            re.search(
                r"\b(?:reuse|reused|previous|last\s+\d+|history|dipakai ulang|digunakan kembali|terakhir)\b",
                normalized,
            )
        )
    if canonical == "hotel_limit":
        return (
            "hotel" in normalized
            and bool(NUMBER_PATTERN.search(content))
            and bool(re.search(r"\b(?:per night|nightly|capped|maximum|max|per malam|maksimal|dibatasi)\b", normalized))
        )
    if canonical == "database_platform":
        return bool(re.search(r"\b(?:database|datastore|postgresql|mysql|sqlite|oracle|sql server)\b", normalized))
    if canonical == "onboarding_documents":
        document_markers = (
            "valid id",
            "tax id",
            "npwp",
            "bank account details",
            "rekening bank",
        )
        return contains_alias(content, CONCEPT_ALIASES[canonical]) or sum(
            marker in normalized for marker in document_markers
        ) >= 2
    return contains_alias(content, CONCEPT_ALIASES[canonical])




def _has_unanswered_relevant_faq_question(
    required: list[str],
    content: str,
) -> bool:
    """Reject a FAQ chunk that contains the relevant Q: but not its paired A:.

    Long TXT FAQ files can be split exactly between a question and its answer.
    A neighbouring answer chunk may still be retrievable, but the question-only
    chunk must not be marked as supporting evidence merely because its wording
    overlaps the user query.
    """
    if not required:
        return False

    text = str(content or "")
    question_markers = list(
        re.finditer(r"(?:^|\s)Q:\s*", text, flags=re.I)
    )
    if not question_markers:
        return False

    for index, marker in enumerate(question_markers):
        segment_end = (
            question_markers[index + 1].start()
            if index + 1 < len(question_markers)
            else len(text)
        )
        segment = text[marker.end():segment_end]
        answer_marker = re.search(r"(?:^|\s)A:\s*", segment, flags=re.I)
        question_part = (
            segment[:answer_marker.start()]
            if answer_marker
            else segment
        )
        relevant = any(
            _concept_match(canonical, question_part)
            for canonical in required
            if canonical in HARD_CONCEPTS
        )
        if relevant and answer_marker is None:
            return True

    return False


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


def _subject_conflicts(required: list[str], content: str) -> list[str]:
    required_set = set(required)
    content_concepts = set(concepts_in_text(content))
    conflicts: list[str] = []
    for group in MUTUALLY_EXCLUSIVE_CONCEPT_GROUPS:
        requested = required_set.intersection(group)
        if not requested:
            continue
        present_requested = content_concepts.intersection(requested)
        present_rivals = content_concepts.intersection(group - requested)
        if not present_requested and present_rivals:
            conflicts.extend(
                f"conflicting_concept:{concept}"
                for concept in sorted(present_rivals)
            )
    return conflicts


def verify_evidence(
    question: str,
    content: str,
    *,
    minimum_score: float = 0.58,
    semantic_score: float | None = None,
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
            semantic_support=0.0,
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

    if _has_unanswered_relevant_faq_question(required, content_text):
        hard_failures.append("faq_question_without_answer")

    hard_failures.extend(_subject_conflicts(required, content_text))

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
            or RELATIVE_DATE_TIME_PATTERN.search(content_text)
            or VERSION_PATTERN.search(content_text)
        ) else 0.0

    semantic_support = _clamp_score(semantic_score)

    if required:
        if semantic_support > 0.0:
            # Concepts remain the primary guardrail. The multilingual semantic
            # signal only replaces part of the literal-overlap weight, so a high
            # embedding score can never override a missing hard concept.
            concept_weight = 0.58
            lexical_weight = 0.12
            numeric_weight = 0.15
            semantic_weight = 0.15
        else:
            concept_weight = 0.68
            lexical_weight = 0.17
            numeric_weight = 0.15
            semantic_weight = 0.0
    else:
        if semantic_support > 0.0:
            # Unknown vocabulary is the main multilingual failure mode. When a
            # candidate comes from the configured multilingual embedding model,
            # semantic relevance is the language-independent evidence signal.
            # The acceptance threshold itself is unchanged.
            concept_weight = 0.0
            lexical_weight = 0.13
            numeric_weight = 0.15
            semantic_weight = 0.72
        else:
            # Standalone verification without a retrieval score preserves the
            # original lexical fallback behavior.
            concept_weight = 0.25
            lexical_weight = 0.60
            numeric_weight = 0.15
            semantic_weight = 0.0

    score = (
        concept_weight * concept_coverage
        + lexical_weight * lexical_coverage
        + numeric_weight * numeric_support
        + semantic_weight * semantic_support
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
        semantic_support=round(semantic_support, 6),
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
            semantic_score=chunk.get("semanticScore"),
        )
        hard_failures = list(decision.hard_failures)
        contradictions = [
            item for item in hard_failures
            if item.startswith("conflicting_concept:")
        ]
        annotated.append(
            {
                **chunk,
                "evidenceSupported": decision.supported,
                "evidenceScore": decision.score,
                "evidenceCoverage": decision.concept_coverage,
                "evidenceSemanticSupport": decision.semantic_support,
                "evidenceMissingConcepts": list(decision.missing_concepts),
                # Missing evidence may be supplied by another chunk. A direct
                # subject conflict, such as mailbox quota for a file-upload-size
                # question, is a contradiction and is removed before generation.
                "evidenceMissingRequirements": hard_failures,
                "evidenceHardFailures": [],
                "evidenceContradictions": contradictions,
                "evidenceHardContradictions": contradictions,
                "evidenceReason": decision.reason,
            }
        )
    return annotated
