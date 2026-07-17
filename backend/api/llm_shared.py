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

SYSTEM_PROMPT = (
    "You are a strict enterprise Retrieval-Augmented Generation assistant. "
    "Use only the supplied evidence. Do not use outside knowledge. "
    "Return the direct answer only. Prefer the wording and terminology used in the evidence. "
    "For a single-fact question, write one concise sentence. For a multi-part or list question, "
    "write only the minimum sentences or bullets needed to cover every requested part. "
    "Do not add an introduction, rationale, recommendation, citation, confidence, heading, label, "
    "assumption, example, condition, exception, background detail, causal explanation, benefit, or "
    "implication unless the question explicitly asks for it and the evidence explicitly states it. "
    "Never replace a supported answer with a refusal."
)


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
            f"[KONTEKS {index}]\n"
            f"Dokumen: {name}\n"
            f"Halaman/lokasi: {page}\n"
            f"Bukti: {content}"
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
    words = clean_answer.split()
    if len(words) < 6:
        return True
    lower_answer = clean_answer.casefold()
    incomplete_endings = (":", ",", ";", "-", " dan", " atau")
    if lower_answer.endswith(incomplete_endings):
        return True
    return False


def build_user_prompt(question: str, context: str, language: str) -> str:
    is_english = language.upper() == "EN"
    if is_english:
        return (
            f"QUESTION:\n{question}\n\n"
            f"EVIDENCE:\n{context}\n\n"
            "Write the shortest complete answer in English. Output answer text only."
        )
    return (
        f"PERTANYAAN:\n{question}\n\n"
        f"BUKTI:\n{context}\n\n"
        "Tulis jawaban lengkap yang paling singkat dalam Bahasa Indonesia. Keluarkan teks jawaban saja."
    )
