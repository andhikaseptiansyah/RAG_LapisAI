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
from api.build_info import BUILD_VERSION
from api.follow_up_service import build_dataset_follow_up_question
from api.language import answer_matches_requested_language, resolve_response_language
from api.model_router import build_grounded_answer, resolve_provider
from retrieval.answerability import apply_answerability_gate
from retrieval.context_selector import select_context_bundle
from retrieval.hybrid_search import _apply_evidence_verification, hybrid_search
from retrieval.query_expansion import (
    build_natural_bridge_query,
    normalize_text,
    requires_language_bridge,
)
from uploads.config import (
    CONTEXT_REDUNDANCY_THRESHOLD,
    CONTEXT_SECONDARY_SCORE_RATIO,
    MAX_GENERATION_CONTEXTS,
    MAX_SOURCE_CITATIONS,
    MIN_RESULT_SCORE,
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


def _build_language_retry_chunks(
    question: str,
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build a minimal evidence bundle for a language-only generation retry.

    The first generation can fail when a local model copies the source language
    from a long chunk. Retrying with the same verified facts in a smaller bundle
    improves translation compliance without changing retrieval thresholds or
    adding any outside information.
    """
    retry_chunks: list[dict[str, Any]] = []
    for chunk in chunks[:2]:
        raw_content = str(chunk.get("content") or "").strip()
        excerpt = build_evidence_excerpt(
            question,
            raw_content,
            max_chars=700,
        ) or raw_content
        if not excerpt:
            continue

        cloned = dict(chunk)
        cloned["content"] = excerpt
        metadata = dict(chunk.get("metadata") or {})
        metadata["content"] = excerpt
        cloned["metadata"] = metadata
        retry_chunks.append(cloned)
    return retry_chunks


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
        "buildVersion": BUILD_VERSION,
        "retrieval_mode": "refused",
        "retrieval_query": "",
    }


def _retrieve_with_language_fallback(
    question: str,
    *,
    top_k: int,
) -> tuple[list[dict[str, Any]], str, str]:
    """Retrieve with the original question, then a natural English bridge.

    The second pass is attempted only when the normal multilingual pipeline
    returns no accepted evidence. It uses the exact same retrieval, evidence,
    and answerability thresholds. Returned bridge candidates are verified again
    against the original user question before generation, so translated query
    wording cannot weaken subject constraints such as P1 versus P2.
    """
    requested_k = max(top_k, MAX_GENERATION_CONTEXTS)
    primary = hybrid_search(question, top_k=requested_k)
    if primary:
        return primary, "original", question

    if not requires_language_bridge(question):
        return [], "original", question

    bridge_query = build_natural_bridge_query(question)
    if (
        not bridge_query
        or normalize_text(bridge_query) == normalize_text(question)
    ):
        return [], "original", question

    print(
        "[RETRIEVAL] original query rejected; retrying natural language bridge: "
        f"{bridge_query}"
    )
    bridge_candidates = hybrid_search(
        bridge_query,
        top_k=requested_k,
    )
    if not bridge_candidates:
        return [], "natural_language_bridge", bridge_query

    # Re-run deterministic evidence and answerability checks using the original
    # Indonesian question. This retains all existing thresholds and hard
    # constraints while allowing the English retrieval representation to find
    # the correct chunk.
    reverified = _apply_evidence_verification(
        question,
        [dict(candidate) for candidate in bridge_candidates],
        min_score=MIN_RESULT_SCORE,
    )
    reverified = apply_answerability_gate(question, reverified)
    if not reverified:
        print(
            "[RETRIEVAL] natural bridge candidates failed original-question "
            "evidence verification"
        )
        return [], "natural_language_bridge", bridge_query

    return [
        {
            **candidate,
            "retrievalFallbackApplied": True,
            "retrievalOriginalQuestion": question,
            "retrievalBridgeQuery": bridge_query,
        }
        for candidate in reverified
    ], "natural_language_bridge", bridge_query


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
    normalized_language = resolve_response_language(question, requested_language)
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
            "buildVersion": BUILD_VERSION,
        }

    retrieved_chunks, retrieval_mode, retrieval_query = _retrieve_with_language_fallback(
        question,
        top_k=top_k,
    )
    chunks = select_context_bundle(
        question,
        retrieved_chunks,
        max_contexts=MAX_GENERATION_CONTEXTS,
        redundancy_threshold=CONTEXT_REDUNDANCY_THRESHOLD,
        secondary_score_ratio=CONTEXT_SECONDARY_SCORE_RATIO,
    )

    bundle_answerable = has_answerable_evidence(chunks)
    if not chunks or not bundle_answerable:
        payload = _refusal_payload(started_at, normalized_language)
        payload["retrieval_mode"] = retrieval_mode
        payload["retrieval_query"] = retrieval_query
        return payload

    confidence = round(top_confidence(chunks, question=question), 4)
    generation_contexts = _build_generation_contexts(question, chunks)
    if confidence <= 0.0 or not generation_contexts:
        payload = _refusal_payload(started_at, normalized_language)
        payload["retrieval_mode"] = retrieval_mode
        payload["retrieval_query"] = retrieval_query
        return payload

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
    used_language_retry = False
    answer = native_answer
    native_language_ok = bool(
        answer and answer_matches_requested_language(answer, normalized_language)
    )
    if evaluation_mode:
        if not answer:
            raise RuntimeError("Native model generation returned an empty answer")
        if not native_language_ok:
            raise RuntimeError("Native model generation used the wrong output language")
    elif not answer or is_refusal_answer(answer) or not native_language_ok:
        retry_chunks = _build_language_retry_chunks(question, chunks)
        if retry_chunks:
            retry_answer = answer_text_only(
                build_grounded_answer(
                    question,
                    retry_chunks,
                    language=normalized_language,
                    model=selected_provider,
                    evaluation_mode=False,
                )
            )
            if (
                retry_answer
                and not is_refusal_answer(retry_answer)
                and answer_matches_requested_language(
                    retry_answer,
                    normalized_language,
                )
            ):
                answer = retry_answer
                used_language_retry = True

        if not used_language_retry:
            answer = answer_text_only(
                build_safe_extractive_answer(question, chunks, language=normalized_language)
            )
            used_extractive_fallback = bool(answer and not is_refusal_answer(answer))

    if answer and not answer_matches_requested_language(answer, normalized_language):
        print(
            "[CHAT] extractive fallback rejected because it does not match "
            f"requested language={normalized_language}"
        )
        answer = ""
        used_extractive_fallback = False

    sources = build_sources(
        chunks,
        question=question,
        limit=min(MAX_SOURCE_CITATIONS, 2),
    )

    if not answer or is_refusal_answer(answer) or not sources:
        payload = _refusal_payload(started_at, normalized_language)
        payload["retrieval_mode"] = retrieval_mode
        payload["retrieval_query"] = retrieval_query
        return payload

    follow_up_question = build_dataset_follow_up_question(
        question=question,
        answer=answer,
        sources=sources,
        language=normalized_language,
    )

    if used_language_retry:
        generation_mode = "language_repair_retry"
    elif used_extractive_fallback:
        generation_mode = "extractive_fallback"
    else:
        generation_mode = "native_model"

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
        "buildVersion": BUILD_VERSION,
        "retrieval_mode": retrieval_mode,
        "retrieval_query": retrieval_query,
    }
