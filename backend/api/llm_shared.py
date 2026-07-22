"""Shared utilities for LLM client modules."""

import re
from typing import Any

from api.answer_formatter import (
    answer_text_only,
    build_evidence_excerpt,
    build_refusal_answer,
    build_safe_extractive_answer,
    is_refusal_answer,
)
from uploads.config import MAX_GENERATION_CONTEXTS

MAX_CONTEXT_CHARS_PER_CHUNK = 1400
MAX_CONTEXT_CHUNKS = MAX_GENERATION_CONTEXTS
MAX_ANSWER_CHARS = 900

BASE_SYSTEM_PROMPT = (
    "You are a strict enterprise Retrieval-Augmented Generation assistant. "
    "Use only the supplied evidence. Do not use outside knowledge. "
    "Return the direct answer only. Preserve the evidence facts and technical terminology, but translate ordinary wording into the required output language. "
    "For a single-fact question, write one concise sentence. For a multi-part or list question, "
    "write only the minimum sentences or bullets needed to cover every requested part. "
    "Do not add an introduction, rationale, recommendation, citation, confidence, heading, label, "
    "assumption, example, condition, exception, background detail, causal explanation, benefit, or "
    "implication unless the question explicitly asks for it and the evidence explicitly states it. "
    "Never replace a supported answer with a refusal. "
    "Answer in the language explicitly requested in the user prompt. "
    "Do not copy headings, FAQ questions, separators, or unrelated context into the answer."
)


def build_system_prompt(language: str) -> str:
    if str(language).upper() == "EN":
        language_rule = (
            "MANDATORY OUTPUT LANGUAGE: English only. Translate Indonesian evidence into "
            "natural English. Do not output Indonesian sentences. "
        )
    else:
        language_rule = (
            "MANDATORY OUTPUT LANGUAGE: Bahasa Indonesia only. Translate English evidence "
            "into natural Bahasa Indonesia. Do not copy English sentences, except proper "
            "names, product names, codes, and acronyms. "
        )
    return language_rule + BASE_SYSTEM_PROMPT


# Kept for modules outside the main router that still import the constant.
SYSTEM_PROMPT = build_system_prompt("ID")


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def build_context(question: str, chunks: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(chunks[:MAX_CONTEXT_CHUNKS], start=1):
        raw_content = clean_text(chunk.get("content"))
        if not raw_content:
            continue
        content = clean_text(build_evidence_excerpt(question, raw_content)) or raw_content
        if len(content) > MAX_CONTEXT_CHARS_PER_CHUNK:
            content = content[:MAX_CONTEXT_CHARS_PER_CHUNK].rsplit(" ", 1)[0] + "…"

        metadata = chunk.get("metadata") or {}
        name = (
            chunk.get("documentName")
            or chunk.get("document_name")
            or metadata.get("filename")
            or "-"
        )
        page = chunk.get("page", metadata.get("page")) or "-"
        blocks.append(
            f"[EVIDENCE {index}]\n"
            f"Document: {name}\n"
            f"Page/location: {page}\n"
            f"Evidence text: {content}"
        )
    return "\n\n".join(blocks)


def build_grounding_chunks(
    question: str,
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grounded_chunks: list[dict[str, Any]] = []
    for chunk in chunks[:MAX_CONTEXT_CHUNKS]:
        raw_content = clean_text(chunk.get("content"))
        if not raw_content:
            continue

        excerpt = clean_text(build_evidence_excerpt(question, raw_content)) or raw_content
        if len(excerpt) > MAX_CONTEXT_CHARS_PER_CHUNK:
            excerpt = (
                excerpt[:MAX_CONTEXT_CHARS_PER_CHUNK]
                .rsplit(" ", 1)[0]
                .strip()
                + "?"
            )

        cloned_chunk = dict(chunk)
        cloned_chunk["content"] = excerpt
        metadata = dict(chunk.get("metadata") or {})
        metadata["content"] = excerpt
        cloned_chunk["metadata"] = metadata
        grounded_chunks.append(cloned_chunk)

    return grounded_chunks


def clean_model_answer(answer: str) -> str:
    text = answer_text_only(answer)
    if len(text) > MAX_ANSWER_CHARS:
        text = text[:MAX_ANSWER_CHARS].rsplit(" ", 1)[0].strip() + "…"
    return text


def fallback_answer(question: str, chunks: list[dict[str, Any]], language: str) -> str:
    answer = clean_model_answer(
        build_safe_extractive_answer(question, chunks, language=language)
    )
    if not answer or is_refusal_answer(answer):
        return build_refusal_answer(language)
    return answer


def is_incomplete_answer(question: str, answer: str) -> bool:
    clean_answer = clean_text(answer)
    if not clean_answer:
        return True

    lower_answer = clean_answer.casefold()
    incomplete_endings = (":", ",", ";", "-", " dan", " atau", " and", " or")
    if lower_answer.endswith(incomplete_endings):
        return True

    words = clean_answer.split()
    if len(words) < 6:
        # Direct fact answers such as ``50 GB.``, ``PostgreSQL.``, or
        # ``Within four hours.`` are complete even though they are short.
        fragment_tail = {
            "the", "a", "an", "of", "to", "in", "on", "for", "with",
            "is", "are", "was", "were", "and", "or", "yang", "dan",
            "atau", "dengan", "untuk", "dalam", "adalah",
        }
        last_word = re.sub(r"[^a-zà-ÿ]+", "", words[-1].casefold())
        has_terminal_punctuation = clean_answer[-1:] in ".!?"
        if has_terminal_punctuation and last_word not in fragment_tail:
            return False
        if re.search(
            r"(?:\b\d+(?:[.,]\d+)?\s*(?:kb|mb|gb|tb|%|minutes?|hours?|days?|weeks?|months?|years?|menit|jam|hari|bulan|tahun)\b|"
            r"https?://|\b[A-Z][A-Za-z0-9_.-]{2,}\b)",
            clean_answer,
            flags=re.I,
        ):
            return False
        return True

    return False


def build_user_prompt(question: str, context: str, language: str) -> str:
    is_english = language.upper() == "EN"
    if is_english:
        return (
            "OUTPUT LANGUAGE: ENGLISH ONLY.\n"
            f"QUESTION:\n{question}\n\n"
            f"EVIDENCE:\n{context}\n\n"
            "Translate any Indonesian evidence needed for the answer. Write the shortest "
            "complete answer in English. Output answer text only. ENGLISH ONLY."
        )
    return (
        "BAHASA KELUARAN: BAHASA INDONESIA SAJA.\n"
        f"PERTANYAAN:\n{question}\n\n"
        f"BUKTI:\n{context}\n\n"
        "Terjemahkan bukti berbahasa Inggris yang diperlukan. Tulis jawaban lengkap yang "
        "paling singkat dalam Bahasa Indonesia. Jangan menyalin kalimat bahasa Inggris, "
        "kecuali nama diri, nama produk, kode, dan akronim. Keluarkan teks jawaban saja. "
        "BAHASA INDONESIA SAJA."
    )


def build_language_repair_prompt(
    question: str,
    context: str,
    previous_answer: str,
    language: str,
) -> str:
    if str(language).upper() == "EN":
        instruction = (
            "Rewrite the answer in English only. Translate all ordinary Indonesian wording. "
            "Preserve every supported fact, number, date, unit, proper name, product name, "
            "code, and acronym. Do not add facts. Output the rewritten answer only."
        )
    else:
        instruction = (
            "Tulis ulang jawaban hanya dalam Bahasa Indonesia. Terjemahkan seluruh kata dan "
            "kalimat bahasa Inggris yang umum. Pertahankan semua fakta, angka, tanggal, satuan, "
            "nama diri, nama produk, kode, dan akronim yang didukung bukti. Jangan menambah "
            "fakta. Keluarkan hanya jawaban hasil penulisan ulang."
        )
    return (
        f"{build_user_prompt(question, context, language)}\n\n"
        f"PREVIOUS ANSWER WITH WRONG LANGUAGE:\n{previous_answer}\n\n"
        f"MANDATORY LANGUAGE CORRECTION:\n{instruction}"
    )
