"""Post-generation grounding checks.

Retrieval gates decide whether an answer may exist. This module checks the text
produced by the LLM before it is returned. Explicit numbers, money, percentages,
versions, URLs, emails, years, and acronyms must be traceable to the selected
context. Unsupported output is rejected and replaced by the extractive fallback.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from retrieval.query_expansion import concepts_in_text, normalize_text
from retrieval.requirements import (
    EMAIL_PATTERN,
    URL_PATTERN,
    extract_evidence_requirements,
    is_scenario_comparison,
    requirement_satisfied,
)
from uploads.config import GENERATION_MIN_CLAIM_SUPPORT


@dataclass(frozen=True)
class GroundingValidation:
    supported: bool
    score: float
    reasons: tuple[str, ...]
    unsupported_facts: tuple[str, ...]
    unsupported_claims: tuple[str, ...]
    missing_answer_requirements: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "reasons",
            "unsupported_facts",
            "unsupported_claims",
            "missing_answer_requirements",
        ):
            payload[key] = list(payload[key])
        return payload


STOPWORDS = {
    "yang", "dan", "atau", "adalah", "dengan", "untuk", "dalam", "pada", "dari",
    "ke", "sebagai", "oleh", "ini", "itu", "tersebut", "harus", "dapat", "akan",
    "the", "and", "or", "is", "are", "was", "were", "with", "for", "to", "in",
    "on", "of", "by", "this", "that", "must", "can", "will", "a", "an",
}

# Numbers with optional currency/unit. Bare numbers are retained because counts,
# dates, thresholds, and identifiers are frequent in enterprise documents.
NUMBER_CORE = r"(?:\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)"
FACT_PATTERN = re.compile(
    rf"(?:\b(?:IDR|Rp\.?|USD|EUR)\s*)?"
    rf"\b{NUMBER_CORE}(?:\s*[x×]\s*{NUMBER_CORE})?"
    r"(?:\s*(?:%|persen|percent|percentage|ribu|thousand|juta|million|miliar|billion|"
    r"triliun|trillion|menit|minutes?|jam|hours?|hari(?:\s+kerja)?|days?|minggu|weeks?|"
    r"bulan|months?|tahun|years?|gb|mb|tb|kb|characters?|karakter|customers?|pelanggan))?\b",
    flags=re.I,
)
ACRONYM_PATTERN = re.compile(r"\b[A-Z][A-Z0-9/-]{1,9}\b")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+|\s+[•-]\s+")


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _tokenize(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9à-ÿ]+", normalize_text(value))
        if len(token) >= 3 and token not in STOPWORDS
    }


def _canonical_fact(value: str) -> str:
    text = normalize_text(value)
    text = text.replace("rp.", "idr ").replace("rp ", "idr ")
    text = re.sub(r"\bpersen(?:tase)?\b|\bpercent(?:age)?\b", "%", text)
    replacements = {
        "miliar": "billion", "juta": "million", "triliun": "trillion",
        "working days": "days", "business days": "days",
        "hari kerja": "days", "hari": "days", "day": "days",
        "jam": "hours", "hour": "hours", "hrs": "hours",
        "menit": "minutes", "minute": "minutes", "mins": "minutes",
        "minggu": "weeks", "week": "weeks",
        "bulan": "months", "month": "months",
        "tahun": "years", "year": "years",
        "karakter": "characters", "character": "characters",
        "pelanggan": "customers", "customer": "customers",
    }
    for source, target in replacements.items():
        text = re.sub(rf"\b{re.escape(source)}\b", target, text)
    # Decimal comma and decimal point are equivalent for comparison.
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    text = re.sub(r"\s*%", "%", text)
    text = re.sub(r"\s+", " ", text).strip(" .,:;()[]")
    # normalize thousands separators removed by normalize_text (2,000,000 ->
    # 2 000 000) into one stable integer token. Repeat for multiple groups.
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"(?<=\d)\s(?=\d{3}(?:\s|$))", "", text)
    return text


def _facts(value: str) -> list[str]:
    output: list[str] = []
    for match in FACT_PATTERN.finditer(str(value or "")):
        fact = _canonical_fact(match.group(0))
        if fact and fact not in output:
            output.append(fact)
    return output


def _context_text(chunks: list[dict[str, Any]]) -> str:
    selected = [
        chunk for chunk in chunks
        if chunk.get("answerabilityEvidenceSelected", True)
        and not chunk.get("evidenceHardFailures")
    ] or [chunk for chunk in chunks if not chunk.get("evidenceHardFailures")]
    return "\n".join(_clean(chunk.get("content")) for chunk in selected if _clean(chunk.get("content")))


def _fact_supported(
    fact: str,
    context: str,
    context_facts: set[str],
    question_facts: set[str],
) -> bool:
    # Facts may come from the verified context or from an explicit scenario value
    # supplied by the user. This permits comparisons such as "12 days" against a
    # policy threshold while still rejecting newly invented quantities.
    if fact in context_facts or fact in question_facts:
        return True

    # A bare number may be a concise restatement of a contextual count. A number
    # carrying currency, percentage, duration, storage, or another unit must match
    # the full canonical fact, otherwise "50 days" could incorrectly pass because
    # the context contains "50 GB".
    residue = re.sub(r"\d+(?:[.]\d+)*", "", fact)
    residue = re.sub(r"[\s.,x×-]+", "", residue)
    if residue:
        return False

    numbers = re.findall(r"\d+(?:\.\d+)*", fact)
    searchable = f"{_canonical_fact(context)} {' '.join(sorted(question_facts))}"
    return bool(numbers) and all(
        re.search(rf"(?<!\d){re.escape(number)}(?!\d)", searchable)
        for number in numbers
    )


def _claim_support(claim: str, context: str) -> float:
    claim_tokens = _tokenize(claim)
    if not claim_tokens:
        return 1.0
    context_tokens = _tokenize(context)
    lexical = len(claim_tokens.intersection(context_tokens)) / len(claim_tokens)

    claim_concepts = set(concepts_in_text(claim))
    context_concepts = set(concepts_in_text(context))
    concept = (
        len(claim_concepts.intersection(context_concepts)) / len(claim_concepts)
        if claim_concepts else 0.0
    )
    return max(lexical, concept)


def validate_grounded_answer(
    question: str,
    answer: str,
    chunks: list[dict[str, Any]],
    *,
    minimum_claim_support: float = GENERATION_MIN_CLAIM_SUPPORT,
) -> GroundingValidation:
    clean_answer = _clean(answer)
    context = _context_text(chunks)
    if not clean_answer or not context:
        return GroundingValidation(
            supported=False,
            score=0.0,
            reasons=("empty_answer_or_context",),
            unsupported_facts=(),
            unsupported_claims=(),
            missing_answer_requirements=(),
        )

    context_normalized = normalize_text(context)
    claim_reference = f"{context}\n{question}" if is_scenario_comparison(question) else context
    context_facts = set(_facts(context))
    question_facts = set(_facts(str(question or "")))
    unsupported_facts: list[str] = []

    for url in URL_PATTERN.findall(clean_answer):
        normalized = url.rstrip(".,);]").casefold()
        if normalized not in context.casefold():
            unsupported_facts.append(url)
    for email in EMAIL_PATTERN.findall(clean_answer):
        if email.casefold() not in context.casefold():
            unsupported_facts.append(email)
    for fact in _facts(clean_answer):
        if not _fact_supported(fact, context, context_facts, question_facts):
            unsupported_facts.append(fact)

    # Acronyms and product/system identifiers must be literal. Common currencies
    # and units are already handled as numeric facts and are excluded here.
    ignored_acronyms = {"IDR", "USD", "EUR", "WIB", "GB", "MB", "TB", "KB"}
    for acronym in ACRONYM_PATTERN.findall(clean_answer):
        if acronym in ignored_acronyms:
            continue
        if (
            re.search(rf"\b{re.escape(acronym)}\b", context, flags=re.I) is None
            and re.search(rf"\b{re.escape(acronym)}\b", str(question or ""), flags=re.I) is None
        ):
            unsupported_facts.append(acronym)

    unsupported_claims: list[str] = []
    claim_scores: list[float] = []
    for raw_claim in SENTENCE_SPLIT.split(str(answer or "")):
        claim = _clean(raw_claim).lstrip("-• ")
        if len(claim.split()) < 4:
            continue
        score = _claim_support(claim, claim_reference)
        claim_scores.append(score)
        # Claims containing a fully supported exact fact may use different
        # bilingual wording, so allow a slightly lower lexical threshold.
        has_fact = bool(_facts(claim) or URL_PATTERN.search(claim) or EMAIL_PATTERN.search(claim))
        threshold = minimum_claim_support * (0.65 if has_fact else 1.0)
        if score + 1e-9 < threshold:
            unsupported_claims.append(claim[:220])

    missing_requirements: list[str] = []
    for requirement in extract_evidence_requirements(question):
        if not requirement.key.startswith("answer_"):
            continue
        if not requirement_satisfied(requirement, [clean_answer]):
            missing_requirements.append(requirement.key)

    reasons: list[str] = []
    if unsupported_facts:
        reasons.append("unsupported_explicit_facts")
    if unsupported_claims:
        reasons.append("unsupported_claims")
    if missing_requirements:
        reasons.append("incomplete_answer_type")

    unique_facts = tuple(dict.fromkeys(unsupported_facts))
    unique_claims = tuple(dict.fromkeys(unsupported_claims))
    unique_missing = tuple(dict.fromkeys(missing_requirements))
    mean_claim = sum(claim_scores) / len(claim_scores) if claim_scores else 1.0
    penalty = min(1.0, 0.28 * len(unique_facts) + 0.22 * len(unique_claims) + 0.25 * len(unique_missing))
    score = max(0.0, min(mean_claim * (1.0 - penalty), 1.0))

    return GroundingValidation(
        supported=not reasons,
        score=round(score, 6),
        reasons=tuple(reasons),
        unsupported_facts=unique_facts,
        unsupported_claims=unique_claims,
        missing_answer_requirements=unique_missing,
    )
