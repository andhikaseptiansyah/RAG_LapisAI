"""Deterministic response-language resolution for Indonesian and English.

The frontend may still send an explicit language preference, but a clearly
English question should not receive Indonesian boilerplate, and vice versa.
The detector is deliberately lightweight and dependency-free.
"""

from __future__ import annotations

import re

INDONESIAN_MARKERS = {
    "apa", "apakah", "berapa", "bagaimana", "mengapa", "kenapa", "kapan",
    "dimana", "siapa", "yang", "dan", "atau", "untuk", "dengan", "dalam",
    "pada", "dari", "ke", "di", "tidak", "harus", "bisa", "dapat", "maksimal",
    "minimum", "ukuran", "batas", "dokumen", "perusahaan", "pelanggan",
    "unggah", "unggahan", "berapa", "seberapa", "cepat", "lama",
}

ENGLISH_MARKERS = {
    "what", "which", "how", "why", "when", "where", "who", "is", "are",
    "was", "were", "the", "a", "an", "of", "to", "in", "on", "for",
    "with", "and", "or", "not", "must", "should", "can", "maximum",
    "minimum", "size", "limit", "document", "company", "customer", "portal",
    "upload", "file", "resolved", "acknowledged", "within",
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


def detect_question_language(question: str, fallback: str = "ID") -> str:
    """Return ``ID`` or ``EN`` using conservative lexical evidence."""
    normalized = _normalize(question)
    normalized_fallback = "EN" if str(fallback).upper() == "EN" else "ID"
    if not normalized:
        return normalized_fallback

    if normalized.startswith(ENGLISH_PREFIXES):
        english_prefix_bonus = 3
    else:
        english_prefix_bonus = 0

    if normalized.startswith(INDONESIAN_PREFIXES):
        indonesian_prefix_bonus = 3
    else:
        indonesian_prefix_bonus = 0

    tokens = re.findall(r"[a-z0-9à-ÿ]+", normalized)
    english_score = english_prefix_bonus + sum(token in ENGLISH_MARKERS for token in tokens)
    indonesian_score = indonesian_prefix_bonus + sum(token in INDONESIAN_MARKERS for token in tokens)

    # Common technical words can occur in both languages. Require a meaningful
    # margin before overriding the caller's explicit preference.
    if english_score >= indonesian_score + 2 and english_score >= 3:
        return "EN"
    if indonesian_score >= english_score + 2 and indonesian_score >= 3:
        return "ID"
    return normalized_fallback


def resolve_response_language(question: str, requested_language: str | None) -> str:
    """Resolve the actual language used by the response.

    ``AUTO`` always follows the detected question language. Explicit ``ID`` or
    ``EN`` remains the fallback, but a clearly opposite-language question is
    corrected to prevent mixed-language output.
    """
    requested = str(requested_language or "AUTO").strip().upper()
    fallback = requested if requested in {"ID", "EN"} else "ID"
    return detect_question_language(question, fallback=fallback)
