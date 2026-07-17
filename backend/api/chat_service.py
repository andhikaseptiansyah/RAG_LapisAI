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
from api.model_router import build_grounded_answer
from retrieval.hybrid_search import hybrid_search
from retrieval.context_selector import select_context_bundle
from uploads.config import (
    CONTEXT_REDUNDANCY_THRESHOLD,
    CONTEXT_SECONDARY_SCORE_RATIO,
    MAX_GENERATION_CONTEXTS,
    MAX_SOURCE_CITATIONS,
)



def _build_generation_contexts(
    question: str,
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return the exact compact evidence bundle used by generation.

    Evaluation must consume these contexts from the same /chat request. Running
    retrieval again can produce a different passage and falsely classify a
    correct answer as hallucinated.
    """
    contexts: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for chunk in chunks[:MAX_GENERATION_CONTEXTS]:
        if chunk.get("evidenceHardFailures"):
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
        raw_content = str(
            chunk.get("content")
            or metadata.get("content")
            or ""
        ).strip()

        # This mirrors api.ollama_client._build_context: the same formatter and
        # the same 1,400-character cap are used for the model and evaluator.
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

def run_chat(
    question: str,
    *,
    top_k: int = 5,
    language: str = "ID",
    model: str | None = None,
) -> dict[str, Any]:
    """Run one chat turn and return the canonical backend response payload.

    The answer field only contains the natural-language answer. Citations and
    confidence are always returned in separate fields.
    """
    started_at = time.perf_counter()
    normalized_language = (language or "ID").upper()

    if is_small_talk(question):
        answer = answer_text_only(
            build_small_talk_answer(question, language=normalized_language)
        )
        return {
            "answer": answer,
            "confidence": 1.0,
            "sources": [],
            "generation_contexts": [],
            "follow_up_question": None,
            "response_time_ms": int(round((time.perf_counter() - started_at) * 1000)),
            "model": "system-small-talk",
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
    confidence = round(top_confidence(chunks, question=question), 4)
    generation_contexts = _build_generation_contexts(question, chunks)

    # hybrid_search already applies the answerability gate. Do not create a second
    # refusal solely from UI confidence calibration after that gate accepted the
    # evidence bundle.
    if not chunks or (confidence <= 0.0 and not bundle_answerable):
        return {
            "answer": build_refusal_answer(normalized_language),
            "confidence": 0.0,
            "sources": [],
            "generation_contexts": [],
            "follow_up_question": None,
            "response_time_ms": int(round((time.perf_counter() - started_at) * 1000)),
            "model": "retrieval-refusal",
        }

    answer = answer_text_only(
        build_grounded_answer(
            question,
            chunks,
            language=normalized_language,
            model=model,
        )
    )

    # A model refusal after accepted retrieval is a generation failure. Recover
    # with a verbatim extractive answer instead of converting it into a false
    # refusal.
    if (not answer or is_refusal_answer(answer)) and bundle_answerable:
        answer = answer_text_only(
            build_safe_extractive_answer(
                question,
                chunks,
                language=normalized_language,
            )
        )

    sources = build_sources(
        chunks,
        question=question,
        limit=min(MAX_SOURCE_CITATIONS, 2),
    )

    if not answer or is_refusal_answer(answer) or not sources:
        answer = build_refusal_answer(normalized_language)
        confidence = 0.0
        sources = []

    follow_up_question = None
    if confidence > 0 and sources:
        follow_up_question = build_dataset_follow_up_question(
            question=question,
            answer=answer,
            sources=sources,
            language=normalized_language,
        )

    return {
        "answer": answer,
        "confidence": confidence,
        "sources": sources,
        "generation_contexts": generation_contexts,
        "follow_up_question": follow_up_question,
        "response_time_ms": int(round((time.perf_counter() - started_at) * 1000)),
        "model": f"{model or 'ollama'}-rag" if confidence > 0 else "retrieval-refusal",
    }
