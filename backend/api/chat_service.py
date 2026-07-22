from __future__ import annotations

import time
from typing import Any

from api.answer_formatter import (
    answer_text_only,
    build_evidence_excerpt,
    build_refusal_answer,
    build_safe_extractive_answer,
    build_small_talk_answer,
    build_sources,
    has_answerable_evidence,
    is_refusal_answer,
    is_small_talk,
    top_confidence,
)
from api.follow_up_service import build_dataset_follow_up_question
from api.language import resolve_response_language
from api.model_router import build_grounded_answer, resolve_provider
from retrieval.context_selector import select_context_bundle
from retrieval.hybrid_search import hybrid_search
from uploads.config import (
    AUTO_DETECT_RESPONSE_LANGUAGE,
    CONTEXT_REDUNDANCY_THRESHOLD,
    CONTEXT_SECONDARY_SCORE_RATIO,
    MAX_GENERATION_CONTEXTS,
    MAX_SOURCE_CITATIONS,
)


def _strict_chunk(chunk: dict[str, Any]) -> bool:
    return bool(
        chunk.get("answerabilityAccepted") is True
        and chunk.get("answerabilityEvidenceSelected", True)
        and chunk.get("answerabilityStrictlySupported", chunk.get("evidenceSupported") is True)
        and not chunk.get("evidenceHardFailures")
        and not chunk.get("evidenceHardContradictions")
        and (
            not chunk.get("answerabilityRequiresCoherentEvidence")
            or chunk.get("answerabilityCoherentEvidence") is True
        )
    )


def _build_generation_contexts(
    question: str,
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return the exact, strictly supported evidence used by generation."""
    contexts: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for chunk in chunks[:MAX_GENERATION_CONTEXTS]:
        if not _strict_chunk(chunk):
            continue
        if not chunk.get("contextSelected", True):
            continue

        metadata = chunk.get("metadata") or {}
        document_name = str(
            chunk.get("documentName")
            or chunk.get("document_name")
            or metadata.get("filename")
            or ""
        ).strip()
        page = chunk.get("page", metadata.get("page"))
        raw_content = str(chunk.get("content") or metadata.get("content") or "").strip()

        excerpt = build_evidence_excerpt(question, raw_content) or raw_content
        if len(excerpt) > 1400:
            excerpt = excerpt[:1400].rsplit(" ", 1)[0].strip() + "…"
        if not excerpt:
            continue

        chunk_id = str(
            chunk.get("chunkId")
            or chunk.get("chunk_id")
            or metadata.get("chunk_id")
            or ""
        )
        key = (document_name.casefold(), str(page or ""), excerpt.casefold())
        if key in seen:
            continue
        seen.add(key)
        contexts.append(
            {
                "text": excerpt,
                "document_name": document_name,
                "page": page,
                "chunk_id": chunk_id,
            }
        )

    return contexts


def _refusal_payload(started_at: float, language: str) -> dict[str, Any]:
    return {
        "answer": build_refusal_answer(language),
        "confidence": 0.0,
        "sources": [],
        "generation_contexts": [],
        "follow_up_question": None,
        "response_time_ms": int(round((time.perf_counter() - started_at) * 1000)),
        "model": "retrieval-refusal",
        "generation_mode": "retrieval_refusal",
        "language": language,
    }


def run_chat(
    question: str,
    *,
    top_k: int = 5,
    language: str = "AUTO",
    model: str | None = None,
    evaluation_mode: bool = False,
) -> dict[str, Any]:
    """Run one grounded chat turn using a strict evidence-first pipeline."""
    started_at = time.perf_counter()
    requested_language = str(language or "AUTO").upper()
    normalized_language = (
        resolve_response_language(question, requested_language)
        if AUTO_DETECT_RESPONSE_LANGUAGE
        else (requested_language if requested_language in {"ID", "EN"} else "ID")
    )
    selected_provider = resolve_provider(model)

    if is_small_talk(question):
        answer = answer_text_only(build_small_talk_answer(question, language=normalized_language))
        return {
            "answer": answer,
            "confidence": 1.0,
            "sources": [],
            "generation_contexts": [],
            "follow_up_question": None,
            "response_time_ms": int(round((time.perf_counter() - started_at) * 1000)),
            "model": "system-small-talk",
            "generation_mode": "system_small_talk",
            "language": normalized_language,
        }

    retrieved_chunks = hybrid_search(question, top_k=max(top_k, MAX_GENERATION_CONTEXTS))
    chunks = select_context_bundle(
        question,
        retrieved_chunks,
        max_contexts=MAX_GENERATION_CONTEXTS,
        redundancy_threshold=CONTEXT_REDUNDANCY_THRESHOLD,
        secondary_score_ratio=CONTEXT_SECONDARY_SCORE_RATIO,
    )

    bundle_answerable = has_answerable_evidence(chunks)
    if not chunks or not bundle_answerable:
        return _refusal_payload(started_at, normalized_language)

    confidence = round(top_confidence(chunks, question=question), 4)
    generation_contexts = _build_generation_contexts(question, chunks)
    if confidence <= 0.0 or not generation_contexts:
        return _refusal_payload(started_at, normalized_language)

    print(
        f"[CHAT] provider={selected_provider} language={normalized_language} "
        f"contexts={len(generation_contexts)} confidence={confidence:.3f}"
    )

    native_answer = answer_text_only(
        build_grounded_answer(
            question,
            chunks,
            language=normalized_language,
            model=selected_provider,
            evaluation_mode=evaluation_mode,
        )
    )

    used_extractive_fallback = False
    answer = native_answer
    if evaluation_mode:
        if not answer:
            raise RuntimeError("Native model generation returned an empty answer")
    elif not answer or is_refusal_answer(answer):
        answer = answer_text_only(
            build_safe_extractive_answer(question, chunks, language=normalized_language)
        )
        used_extractive_fallback = bool(answer and not is_refusal_answer(answer))

    sources = build_sources(
        chunks,
        question=question,
        limit=min(MAX_SOURCE_CITATIONS, 2),
    )

    if not answer or is_refusal_answer(answer) or not sources:
        return _refusal_payload(started_at, normalized_language)

    follow_up_question = build_dataset_follow_up_question(
        question=question,
        answer=answer,
        sources=sources,
        language=normalized_language,
    )

    generation_mode = (
        "native_model"
        if evaluation_mode or not used_extractive_fallback
        else "extractive_fallback"
    )

    return {
        "answer": answer,
        "confidence": confidence,
        "sources": sources,
        "generation_contexts": generation_contexts,
        "follow_up_question": follow_up_question,
        "response_time_ms": int(round((time.perf_counter() - started_at) * 1000)),
        "model": f"{selected_provider}-rag",
        "generation_mode": generation_mode,
        "language": normalized_language,
    }
