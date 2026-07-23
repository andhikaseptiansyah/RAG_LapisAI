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
    build_verified_scalar_answer,
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
from retrieval.hybrid_search import (
    _apply_evidence_verification,
    _base_hybrid_candidates,
    hybrid_search,
)
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


def _refusal_payload(
    started_at: float,
    language: str,
    *,
    failure_stage: str,
) -> dict[str, Any]:
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
        "failure_stage": failure_stage,
    }


def _strict_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only candidates that can safely be used for generation."""
    return [candidate for candidate in candidates if _strict_chunk(candidate)]


def _strip_retrieval_annotations(candidate: dict[str, Any]) -> dict[str, Any]:
    """Remove stale gate metadata before validating a candidate for a new query.

    Bridge candidates may already carry evidence and answerability fields created
    for the English retrieval query. Reusing those fields while checking the
    original Indonesian question can preserve a rejection that no longer applies.
    The raw retrieval scores and document metadata are retained.
    """
    cloned = dict(candidate)
    for key in list(cloned):
        if (
            key.startswith("evidence")
            or key.startswith("answerability")
            or key.startswith("minimumEvidence")
            or key.startswith("preRerankAnswerability")
        ):
            cloned.pop(key, None)
    return cloned


def _validate_for_original_question(
    question: str,
    candidates: list[dict[str, Any]],
    *,
    requested_k: int,
    bridge_query: str,
    stage: str,
) -> list[dict[str, Any]]:
    """Apply all safety gates again using the user's original question."""
    if not candidates:
        return []

    clean_candidates = [
        _strip_retrieval_annotations(candidate)
        for candidate in candidates
    ]
    reverified = _apply_evidence_verification(
        question,
        clean_candidates,
        min_score=MIN_RESULT_SCORE,
    )
    reverified = apply_answerability_gate(question, reverified)
    strict = _strict_candidates(reverified)
    if not strict:
        return []

    strict_ids = {
        str(candidate.get("chunkId") or candidate.get("chunk_id") or "")
        for candidate in strict
    }
    accepted = [
        {
            **candidate,
            "retrievalFallbackApplied": stage != "original",
            "retrievalFallbackStage": stage,
            "retrievalOriginalQuestion": question,
            "retrievalBridgeQuery": bridge_query,
        }
        for candidate in reverified
        if str(candidate.get("chunkId") or candidate.get("chunk_id") or "")
        in strict_ids
    ]
    accepted.sort(
        key=lambda candidate: (
            float(candidate.get("score") or 0.0),
            float(candidate.get("evidenceScore") or 0.0),
            float(candidate.get("baseScore") or 0.0),
        ),
        reverse=True,
    )
    return accepted[:requested_k]


def _retrieve_with_language_fallback(
    question: str,
    *,
    top_k: int,
) -> tuple[list[dict[str, Any]], str, str]:
    """Retrieve normally, then replay a failing Indonesian query in English.

    The bridge pass uses the same complete pipeline as a direct English question,
    because that exact path is known to work in the application. Before the
    bridge candidates are validated against the original Indonesian question,
    all stale evidence and answerability annotations are removed.
    """
    requested_k = max(top_k, MAX_GENERATION_CONTEXTS)

    primary = hybrid_search(question, top_k=requested_k)
    primary_strict = _strict_candidates(primary)
    if primary_strict:
        return primary, "original", question

    if not requires_language_bridge(question):
        return [], "original", question

    bridge_query = build_natural_bridge_query(question)
    if not bridge_query or normalize_text(bridge_query) == normalize_text(question):
        return [], "original", question

    bridge_top_k = max(requested_k * 2, 10)
    bridge_candidate_k = max(bridge_top_k * 4, 40)
    print(
        "[RETRIEVAL] primary Indonesian path has no strict evidence; "
        f"replaying direct English path: {bridge_query}"
    )

    # This deliberately mirrors a successful user-entered English question,
    # including reranking, evidence verification, and English answerability.
    bridge_candidates = hybrid_search(
        bridge_query,
        top_k=bridge_top_k,
        candidate_k=bridge_candidate_k,
        apply_answerability=True,
    )
    accepted = _validate_for_original_question(
        question,
        bridge_candidates,
        requested_k=requested_k,
        bridge_query=bridge_query,
        stage="bridge_direct_english_path",
    )
    if accepted:
        return accepted, "natural_language_bridge", bridge_query

    print(
        "[RETRIEVAL] direct English path was not accepted after Indonesian "
        "revalidation; checking raw English semantic+BM25 union"
    )
    raw_candidate_k = max(bridge_candidate_k * 2, 80)
    raw_candidates = _base_hybrid_candidates(
        bridge_query,
        candidate_k=raw_candidate_k,
    )
    accepted = _validate_for_original_question(
        question,
        raw_candidates,
        requested_k=requested_k,
        bridge_query=bridge_query,
        stage="bridge_raw_union",
    )
    if accepted:
        return accepted, "natural_language_bridge_raw", bridge_query

    return [], "natural_language_bridge_raw", bridge_query


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
        payload = _refusal_payload(
            started_at,
            normalized_language,
            failure_stage="context_or_answerability",
        )
        payload["retrieval_mode"] = retrieval_mode
        payload["retrieval_query"] = retrieval_query
        return payload

    confidence = round(top_confidence(chunks, question=question), 4)
    generation_contexts = _build_generation_contexts(question, chunks)
    if confidence <= 0.0 or not generation_contexts:
        payload = _refusal_payload(
            started_at,
            normalized_language,
            failure_stage="confidence_or_generation_context",
        )
        payload["retrieval_mode"] = retrieval_mode
        payload["retrieval_query"] = retrieval_query
        return payload

    print(
        f"[CHAT] provider={selected_provider} language={normalized_language} "
        f"contexts={len(generation_contexts)} confidence={confidence:.3f}"
    )

    verified_scalar_answer = ""
    if not evaluation_mode:
        verified_scalar_answer = answer_text_only(
            build_verified_scalar_answer(
                question,
                chunks,
                language=normalized_language,
            )
        )

    used_extractive_fallback = False
    used_language_retry = False

    if verified_scalar_answer:
        answer = verified_scalar_answer
        generation_mode = "verified_scalar"
        print(
            "[CHAT] using deterministic verified scalar answer; "
            f"language={normalized_language} answer={answer}"
        )
    else:
        native_answer = answer_text_only(
            build_grounded_answer(
                question,
                chunks,
                language=normalized_language,
                model=selected_provider,
                evaluation_mode=evaluation_mode,
            )
        )

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
                    build_safe_extractive_answer(
                        question,
                        chunks,
                        language=normalized_language,
                    )
                )
                used_extractive_fallback = bool(
                    answer and not is_refusal_answer(answer)
                )

        if answer and not answer_matches_requested_language(answer, normalized_language):
            print(
                "[CHAT] fallback answer rejected because it does not match "
                f"requested language={normalized_language}"
            )
            answer = ""
            used_extractive_fallback = False

        if used_language_retry:
            generation_mode = "language_repair_retry"
        elif used_extractive_fallback:
            generation_mode = "extractive_fallback"
        else:
            generation_mode = "native_model"

    sources = build_sources(
        chunks,
        question=question,
        limit=min(MAX_SOURCE_CITATIONS, 2),
    )

    if not answer or is_refusal_answer(answer) or not sources:
        payload = _refusal_payload(
            started_at,
            normalized_language,
            failure_stage="answer_or_source_build",
        )
        payload["retrieval_mode"] = retrieval_mode
        payload["retrieval_query"] = retrieval_query
        return payload

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
        "model": f"{selected_provider}-rag",
        "generation_mode": generation_mode,
        "language": normalized_language,
        "buildVersion": BUILD_VERSION,
        "retrieval_mode": retrieval_mode,
        "retrieval_query": retrieval_query,
        "failure_stage": None,
    }
