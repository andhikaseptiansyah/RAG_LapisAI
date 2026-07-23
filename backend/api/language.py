"""Deterministic response-language resolution and output-language checks."""

from __future__ import annotations

import re

INDONESIAN_MARKERS = {
    "apa", "apakah", "berapa", "bagaimana", "mengapa", "kenapa", "kapan",
    "dimana", "siapa", "yang", "dan", "atau", "untuk", "dengan", "dalam",
    "pada", "dari", "ke", "di", "tidak", "harus", "bisa", "dapat", "maksimal",
    "minimum", "ukuran", "batas", "dokumen", "perusahaan", "pelanggan",
    "unggah", "unggahan", "seberapa", "cepat", "lama", "adalah", "akan",
    "baru", "masa", "percobaan", "karyawan", "bulan", "minggu", "hari",
    "jam", "menit", "tahun", "sebelum", "setelah", "dilakukan", "selama",
    "berlaku", "memiliki", "menjadi", "jawaban", "informasi", "berdasarkan",
    "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan",
    "sembilan", "sepuluh", "sebelas", "hari", "minggu", "bulan", "tahun",
}

ENGLISH_MARKERS = {
    "what", "which", "how", "why", "when", "where", "who", "is", "are",
    "was", "were", "the", "a", "an", "of", "to", "in", "on", "for",
    "with", "and", "or", "not", "must", "should", "can", "maximum",
    "minimum", "size", "limit", "document", "company", "customer", "portal",
    "upload", "file", "resolved", "acknowledged", "within", "new", "employees",
    "employee", "serve", "serves", "probation", "period", "months", "month",
    "weeks", "week", "days", "day", "hours", "hour", "minutes", "minute",
    "years", "year", "before", "after", "conducted", "during", "applies",
    "has", "have", "becomes", "answer", "information", "based", "formal",
    "performance", "evaluation", "confirmation", "one", "two", "three",
    "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
    "twelve", "days", "weeks", "months", "years",
}

INDONESIAN_PREFIXES = (
    "apa ", "apakah ", "berapa ", "bagaimana ", "mengapa ", "kenapa ",
    "kapan ", "dimana ", "siapa ", "tolong ", "jelaskan ", "sebutkan ",
)

ENGLISH_PREFIXES = (
    "what ", "which ", "how ", "why ", "when ", "where ", "who ",
    "please ", "explain ", "describe ", "list ",
)


def _normalize(value: str) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"[^a-z0-9à-ÿ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _language_scores(value: str) -> tuple[int, int]:
    normalized = _normalize(value)
    if not normalized:
        return 0, 0

    tokens = re.findall(r"[a-z0-9à-ÿ]+", normalized)
    english_score = sum(token in ENGLISH_MARKERS for token in tokens)
    indonesian_score = sum(token in INDONESIAN_MARKERS for token in tokens)

    if normalized.startswith(ENGLISH_PREFIXES):
        english_score += 3
    if normalized.startswith(INDONESIAN_PREFIXES):
        indonesian_score += 3

    # Product names, acronyms, codes, and numbers are neutral. Common affixes
    # provide extra evidence only when enough alphabetic text is present.
    indonesian_score += sum(
        token.startswith(("meng", "meny", "ber", "ter", "diper", "ke"))
        or token.endswith(("nya", "kan", "lah"))
        for token in tokens
        if len(token) >= 5
    )
    english_score += sum(
        token.endswith(("ing", "tion", "ment", "ness", "able"))
        for token in tokens
        if len(token) >= 6
    )
    return english_score, indonesian_score


def detect_question_language(question: str, fallback: str = "ID") -> str:
    normalized = _normalize(question)
    normalized_fallback = "EN" if str(fallback).upper() == "EN" else "ID"
    if not normalized:
        return normalized_fallback

    english_score, indonesian_score = _language_scores(normalized)
    if english_score >= indonesian_score + 2 and english_score >= 3:
        return "EN"
    if indonesian_score >= english_score + 2 and indonesian_score >= 3:
        return "ID"
    return normalized_fallback


def resolve_response_language(question: str, requested_language: str | None) -> str:
    """Use an explicit UI preference exactly; detect only for AUTO or empty values."""
    requested = str(requested_language or "AUTO").strip().upper()
    if requested in {"ID", "EN"}:
        return requested
    return detect_question_language(question, fallback="ID")


def answer_matches_requested_language(answer: str, requested_language: str) -> bool:
    """Return False only when the answer clearly uses the opposite language.

    Very short numeric, code, acronym, or proper-name answers are treated as
    language-neutral and therefore accepted.
    """
    normalized = _normalize(answer)
    if not normalized:
        return False

    target = "EN" if str(requested_language).upper() == "EN" else "ID"
    english_score, indonesian_score = _language_scores(normalized)

    if english_score == 0 and indonesian_score == 0:
        return True

    alphabetic_tokens = [
        token for token in re.findall(r"[a-zà-ÿ]+", normalized)
        if len(token) >= 2
    ]
    enough_language_content = len(alphabetic_tokens) >= 2

    if target == "ID":
        clearly_english = (
            english_score >= indonesian_score + 2
            or (
                enough_language_content
                and indonesian_score == 0
                and english_score >= 1
            )
        )
        return not clearly_english

    clearly_indonesian = (
        indonesian_score >= english_score + 2
        or (
            enough_language_content
            and english_score == 0
            and indonesian_score >= 1
        )
    )
    return not clearly_indonesian
